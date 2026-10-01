import os, re, shlex, shutil, sys, threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from re import Pattern
from typing import Callable, Iterable, TypeVar

import requests
from requests.adapters import HTTPAdapter
from semver import Version
from urllib3.util import Retry

from nexus_azure_migrate.common.models import CustomExtenstion, NexusConfig, UploadablePackage

T = TypeVar("T")

MARKER_PATTERN = re.compile(CustomExtenstion.pattern.value)
VERSION_PATTERN = re.compile(r'\d+\.\d+\.\d+(?:-[\w.-]+)?(?:\+[\w.-]+)?')
DEFAULT_WORKERS = min(32, (os.cpu_count() or 1) + 4)  # same default as ThreadPoolExecutor


def build_session(config: NexusConfig, max_retry: int, max_workers: int | None) -> requests.Session:
    '''
    A session whose connection pool is large enough for every worker thread,
    so connections are reused instead of being re-opened for each artifact.
    '''
    pool_size = max_workers or DEFAULT_WORKERS
    retry_strategy = Retry(
        total=max_retry,
        backoff_factor=0.5,
        status_forcelist=[403, 429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=pool_size, pool_maxsize=pool_size)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.auth = config.auth
    session.verify = config.x509_verify
    return session


def sum_concurrently(fn: Callable[[T], int], items: Iterable[T], max_workers: int | None) -> int:
    '''
    Runs fn over items in a thread pool and returns the sum of the results.
    Unlike executor.map, items are consumed lazily so a generator over a huge
    repository is never fully materialised in memory.
    '''
    total = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        max_in_flight = (max_workers or DEFAULT_WORKERS) * 2
        pending: set[Future[int]] = set()
        for item in items:
            if len(pending) >= max_in_flight:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                total += sum(future.result() for future in done)
            pending.add(executor.submit(fn, item))
        total += sum(future.result() for future in wait(pending).done)
    return total


def path_matches_filter(
        file_path: str, semver: str, version_pattern: Pattern[str],
        allow_invalid_version: bool, name_pattern: Pattern[str],
        name_exclusion_pattern: Pattern[str]) -> bool:
    # artifacts that have already been handled are marked with a CustomExtenstion
    if MARKER_PATTERN.search(file_path):
        return False

    version = get_version_info(get_version_candidates(file_path))
    if version == "":
        if not allow_invalid_version:
            return False
        # skip the version filters for artifacts without a valid semver
        return (
            not os.path.isdir(file_path)
            and bool(name_pattern.search(file_path))
            and not name_exclusion_pattern.search(file_path)
        )
    return (
        bool(name_pattern.search(file_path))
        and not name_exclusion_pattern.search(file_path)
        and bool(version_pattern.search(version))
        and Version.parse(version).match(semver)
        # useful during upload to prevent uploading a directory
        and not os.path.isdir(file_path)
    )


def get_version_candidates(text: str) -> list[str]:
    return VERSION_PATTERN.findall(text)


def get_version_info(version_candidates: list[str]) -> str:
    '''Returns the first candidate that is a valid semver, or ""'''
    for candidate in version_candidates:
        if Version.is_valid(candidate):
            return candidate
    return ""


def command_prefix(command: str) -> list[str]:
    '''
    Splits a user supplied command such as "dotnet nuget" or "python -m twine"
    into tokens. The executable is resolved via PATH so that, on windows,
    "mvn" and "npm" find mvn.cmd and npm.cmd. "python" resolves to the
    interpreter running this tool so twine is always found.
    '''
    tokens = [token.strip('"\'') for token in shlex.split(command, posix=os.name != "nt")]
    if not tokens:
        raise ValueError("command must not be empty")
    if tokens[0] == "python":
        tokens[0] = sys.executable
    else:
        tokens[0] = shutil.which(tokens[0]) or tokens[0]
    return tokens


def extra_args(env: dict[str, str], key: str) -> list[str]:
    return shlex.split(env.get(key, ""), posix=os.name != "nt")


_config_file_lock = threading.Lock()


def create_config_file(
        directory: Path,
        uploadable_artifact: UploadablePackage, file_name: str,
        content: str) -> str:
    '''
    Creates a file with the given content in the folder of the artifact format,
    unless it already has that content. Safe to call from multiple threads.
    Returns the string path of the created file
    '''
    file_path = directory / uploadable_artifact.repo_format / file_name
    with _config_file_lock:
        if not file_path.exists() or file_path.read_text(encoding="utf-8") != content:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
    return str(file_path)
