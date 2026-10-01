from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from rich import print
from semver import Version

from nexus_azure_migrate.common.models import DownloadablePackage, ArtifactMetaData, NexusConfig
from nexus_azure_migrate.common.utils import get_version_info, path_matches_filter


@dataclass
class DirectoryListing:
    relative_path: str
    text: str


class Nexus2Client:
    def __init__(
            self, config: NexusConfig,
            artifact_metadata: ArtifactMetaData,
            session: requests.Session,
            download_package: Callable[[DownloadablePackage], int]):
        self.config = config
        self.artifact_metadata = artifact_metadata
        self.base_url = urljoin(config.url, "service/local/")
        self.session = session
        self.download_package = download_package

    def get(self, endpoint: str, **kwargs: Any) -> requests.Response:
        response = self.session.get(
            urljoin(self.base_url, endpoint.lstrip('/')),
            headers={"Accept": "application/json"}, **kwargs
        )
        response.raise_for_status()
        return response

    def repositories_list(self) -> list[dict[str, str]]:
        return self.get('repositories').json()["data"]

    def download_repo_artifacts(self, repository_id: str, repo_format: str, max_workers: int | None) -> int:
        '''
        Walks the repository tree breadth first. Directory listings and downloads
        share a single thread pool, driven from this thread, so the number of
        threads stays at max_workers however deep the tree is.
        '''
        base_path = f'repositories/{repository_id}/content'
        return_code = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pending: set[Future[Any]] = {
                executor.submit(self.list_directory, base_path, repo_format, DirectoryListing('/', ''), True)
            }
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    result = future.result()
                    if isinstance(result, int):
                        return_code += result
                        continue
                    directories, packages = result
                    pending.update(
                        executor.submit(self.list_directory, base_path, repo_format, directory, False)
                        for directory in directories
                    )
                    pending.update(
                        executor.submit(self.download_package, package)
                        for package in packages
                    )
        return return_code

    def list_directory(
            self, base_path: str, repo_format: str, listing: DirectoryListing, is_root: bool
        ) -> int | tuple[list[DirectoryListing], list[DownloadablePackage]]:
        '''
        Returns the sub-directories to visit and the packages to download,
        or an error code if the directory could not be read.
        '''
        try:
            response_list: list[dict[str, Any]] | None = self.get(
                base_path + listing.relative_path, params={"isLocal": "true"}
            ).json().get('data')
        except requests.RequestException as ex:
            print(f"[red]Error[/red] listing {base_path + listing.relative_path} | {ex}")
            return 7
        if not response_list:
            return 0

        is_final_level = all(item.get('leaf') is True for item in response_list)
        if not is_final_level:
            # files that show up before the final level are discarded, and
            # versions/names are filtered early to avoid walking unwanted folders
            directories = [
                DirectoryListing(item['relativePath'], item['text'])
                for item in response_list
                if item['relativePath'].endswith('/')
                and (is_root or self.match_version_and_name(item['text'], listing.text))
            ]
            return directories, []

        artifact_metadata = self.artifact_metadata
        packages = [
            DownloadablePackage(
                nexus_config=self.config,
                # adapt each item to the nexus3 variables required for download
                package_metadata=metadata | {
                    'path': metadata['relativePath'],
                    'format': repo_format,
                    'downloadUrl': metadata['resourceURI']
                }
            ) for metadata in response_list
            if path_matches_filter(metadata['relativePath'],
                artifact_metadata.semver, artifact_metadata.version_pattern,
                artifact_metadata.allow_invalid_version, artifact_metadata.name_pattern,
                artifact_metadata.name_exclusion_pattern
            )
        ]
        return [], packages

    def match_version_and_name(self, version_prospect: str, parent_text: str) -> bool:
        '''Returns True if the text is not a valid semver, so the folder is still visited'''
        artifact_metadata = self.artifact_metadata
        version = get_version_info([version_prospect])
        if version == "":
            return True
        try:
            return (
                bool(artifact_metadata.version_pattern.search(version))
                and Version.parse(version).match(artifact_metadata.semver)
                and bool(artifact_metadata.name_pattern.search(parent_text))
                and not artifact_metadata.name_exclusion_pattern.search(parent_text)
            )
        except ValueError:
            return True
