import os, re
from pathlib import Path, PurePosixPath
from typing import Callable

import requests
from rich import print

from nexus_azure_migrate.common.Nexus2Client import Nexus2Client
from nexus_azure_migrate.common.Nexus3Client import Nexus3Client
from nexus_azure_migrate.common.models import (
    CustomExtenstion, DownloadablePackage, ArtifactMetaData, NexusConfig, UploadablePackage
)
from nexus_azure_migrate.common.utils import build_session, path_matches_filter, sum_concurrently

# npm scoped paths look like @scope/name/-/name-1.0.0.tgz
UNSAFE_PATH_PATTERN = re.compile(r'-/|@')
CHUNK_SIZE = 1024 * 1024


class DownloadModule:
    def __init__(self, nexus_config: NexusConfig,
            artifact_metadata: ArtifactMetaData,
            upload_artifact: Callable[[UploadablePackage], int]
        ):
        self.nexus_config = nexus_config
        self.artifact_metadata = artifact_metadata
        self.upload_artifact = upload_artifact
        self.session = build_session(nexus_config, artifact_metadata.max_retry, artifact_metadata.max_workers)

    def filter_repositories(self, repositories: list[dict]) -> list[dict]:
        artifact_metadata = self.artifact_metadata
        return [
            repo_dict for repo_dict in repositories
            if artifact_metadata.format_pattern.search(repo_dict['format'])
            and artifact_metadata.repository_pattern.search(repo_dict['name'])
        ]

    def download(self) -> int:
        artifact_metadata = self.artifact_metadata
        nexus_client = Nexus3Client(self.nexus_config, self.session)
        print("Fetching repository list...")
        filtered_repositories = self.filter_repositories(nexus_client.repositories_list())
        print("Fetching artifact list. This may take a while...")
        return_code = 0
        for repo_dict in filtered_repositories:
            try:
                return_code += sum_concurrently(
                    self.download_if_matches,
                    nexus_client.list_assets(repo_dict['name']),
                    artifact_metadata.max_workers,
                )
            except requests.RequestException as ex:
                print(f"[red]Exception[/red] occurred while listing artifacts of repo {repo_dict['name']}")
                print(ex)
                return_code += 1
        return return_code

    def download_if_matches(self, package_metadata: dict[str, str]) -> int:
        artifact_metadata = self.artifact_metadata
        if not path_matches_filter(package_metadata['path'],
                artifact_metadata.semver, artifact_metadata.version_pattern,
                artifact_metadata.allow_invalid_version, artifact_metadata.name_pattern,
                artifact_metadata.name_exclusion_pattern):
            return 0
        return self.download_package(DownloadablePackage(
            nexus_config=self.nexus_config,
            package_metadata=package_metadata,
        ))

    def download_v2(self) -> int:
        artifact_metadata = self.artifact_metadata
        nexus_client = Nexus2Client(
            self.nexus_config, self.artifact_metadata,
            self.session, self.download_package
        )
        print("Fetching repository list...")
        filtered_repositories = self.filter_repositories(nexus_client.repositories_list())
        print("Fetching artifact list. This may take a while...")
        return_code = 0
        for repo_dict in filtered_repositories:
            try:
                return_code += nexus_client.download_repo_artifacts(
                    repo_dict['id'], repo_dict['format'], artifact_metadata.max_workers
                )
            except requests.RequestException as ex:
                print(f"[red]Exception[/red] occurred while listing artifacts of repo {repo_dict['name']}")
                print(ex)
                return_code += 1
        return return_code

    def download_package(self, downloadable_package: DownloadablePackage) -> int:
        artifact_metadata = self.artifact_metadata
        package_metadata = downloadable_package.package_metadata
        # nexus3 paths start with "/", which would otherwise make the path absolute
        file_path = UNSAFE_PATH_PATTERN.sub("", package_metadata['path']).lstrip('/')
        if package_metadata['format'] == 'nuget' and not file_path.endswith('.nupkg'):
            # nexus3 stores nuget packages as <id>/<version> without an extension
            package_id, _, version = file_path.rstrip('/').rpartition('/')
            file_path = f"{file_path}/{package_id.rsplit('/', 1)[-1]}.{version}.nupkg"
        if '..' in PurePosixPath(file_path).parts:
            print(f"[red]Error[/red] refusing to write outside {artifact_metadata.directory}: {package_metadata['path']}")
            return 1
        destination_filepath: Path = artifact_metadata.directory / package_metadata['format'] / file_path

        if any(
            destination_filepath.with_name(destination_filepath.name + marker.value).exists()
            for marker in (CustomExtenstion.uploaded, CustomExtenstion.remote_exists, CustomExtenstion.remote_deleted)
        ):
            print(f"Skipping download: [purple]{file_path}[/purple]"
                + f" - Artifact marked as {CustomExtenstion.uploaded.value}"
                + f" | {CustomExtenstion.remote_exists.value}"
                + f" | {CustomExtenstion.remote_deleted.value}")
            return 0

        if destination_filepath.exists():
            print(f"Artifact already downloaded - {file_path}")
        else:
            try:
                self.download_file(package_metadata['downloadUrl'], destination_filepath)
                print(f"[green]✔[/green] downloaded -> {destination_filepath}")
            except (requests.RequestException, OSError) as ex:
                print(f"[red]Error[/red] downloading file: {package_metadata['downloadUrl']} | {ex}")
                return 1

        if artifact_metadata.eager_upload:
            try:
                return self.upload_artifact(UploadablePackage(
                    repo_format=package_metadata['format'],
                    artifact_path=str(destination_filepath),
                ))
            except Exception as ex:
                print(f"[red]Error[/red] uploading file: {destination_filepath} | {ex}")
                return 4
        return 0

    def download_file(self, url: str, destination_filepath: Path):
        '''
        Streams to a temporary file which is renamed once complete, so an
        interrupted download is never mistaken for a downloaded artifact.
        '''
        destination_filepath.parent.mkdir(parents=True, exist_ok=True)
        partial_filepath = destination_filepath.with_name(destination_filepath.name + ".part")
        try:
            with self.session.get(url, stream=True) as response:
                response.raise_for_status()
                with open(partial_filepath, 'wb') as dest:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        dest.write(chunk)
            os.replace(partial_filepath, destination_filepath)
        finally:
            partial_filepath.unlink(missing_ok=True)
