import json, re, sys
from pathlib import Path

import pytest

from nexus_azure_migrate.common.models import NexusConfig, UploadablePackage
from nexus_azure_migrate.common.utils import (
    command_prefix, create_config_file, get_version_info, path_matches_filter, sum_concurrently
)

ANY = re.compile(".*")
NOTHING = re.compile("exclude-nothing")


def matches(path: str, semver=">=0.0.0", version=ANY, allow_invalid=False, name=ANY, exclude=NOTHING) -> bool:
    return path_matches_filter(path, semver, version, allow_invalid, name, exclude)


@pytest.mark.parametrize("candidates, expected", [
    (["1.2.3"], "1.2.3"),
    (["1.2.3-beta.1+build.5"], "1.2.3-beta.1+build.5"),
    # an invalid candidate must not hide a valid one that follows it
    (["01.2.3", "1.2.3"], "1.2.3"),
    ([], ""),
])
def test_get_version_info(candidates, expected):
    assert get_version_info(candidates) == expected


def test_path_filters():
    path = "maven2/com/example/lib/1.9.40/lib-1.9.40.jar"
    assert matches(path)
    assert matches(path, semver=">=1.9.37")
    assert not matches(path, semver="<1.9.37")
    assert matches(path, name=re.compile(r"\.jar$"))
    assert not matches(path, exclude=re.compile(r"\.jar$"))
    assert not matches(path, version=re.compile(r"^2\."))


def test_marked_artifacts_are_skipped():
    assert not matches("pypi/pkg/1.0.0/pkg-1.0.0.whl.uploaded")
    assert not matches("pypi/pkg/1.0.0/pkg-1.0.0.whl.remote_exists")


def test_invalid_versions():
    assert not matches("nuget/pkg/latest/pkg.nupkg")
    assert matches("nuget/pkg/latest/pkg.nupkg", allow_invalid=True)
    assert not matches("nuget/pkg/latest/pkg.nupkg", allow_invalid=True, exclude=re.compile("pkg"))


def test_command_prefix_resolves_python():
    assert command_prefix("python -m twine") == [sys.executable, "-m", "twine"]


def test_command_prefix_keeps_unknown_executables():
    assert command_prefix("not-a-real-binary --flag")[0] == "not-a-real-binary"


def test_sum_concurrently_is_lazy():
    consumed = []

    def items():
        for i in range(100):
            consumed.append(i)
            yield i

    assert sum_concurrently(lambda i: i % 2, items(), max_workers=2) == 50
    assert len(consumed) == 100


def test_create_config_file_handles_spaces(tmp_path: Path):
    directory = tmp_path / "dir with spaces"
    path = create_config_file(directory, UploadablePackage("npm", "x"), ".npmrc", "content")
    assert Path(path).read_text() == "content"


def test_nexus_config_from_file(tmp_path: Path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"nexus_url": "http://nexus", "nexus_user": "u", "nexus_pass": "p", "nexus_verify": False}))
    config = NexusConfig.from_file(legacy)
    assert (config.url, config.auth, config.x509_verify) == ("http://nexus/", ("u", "p"), False)

    current = tmp_path / "current.json"
    current.write_text(json.dumps({"url": "http://nexus/", "username": "u", "password": "p"}))
    assert NexusConfig.from_file(current).auth == ("u", "p")
