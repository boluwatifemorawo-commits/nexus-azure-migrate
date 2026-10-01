import os, re, subprocess
from typing import Callable, Iterator

from rich import print
from rich.markup import escape

from nexus_azure_migrate.common.models import (
    CustomExtenstion, ArtifactMetaData, UploadCommand,
    UploadablePackage
)
from nexus_azure_migrate.common.utils import path_matches_filter, sum_concurrently
from nexus_azure_migrate.maven2_module import maven2_upload
from nexus_azure_migrate.npm_module import npm_upload
from nexus_azure_migrate.nuget_module import nuget_upload
from nexus_azure_migrate.pypi_module import python_upload

Upload_actions: dict[str, Callable[[ArtifactMetaData, UploadablePackage, dict[str, str]], UploadCommand]] = {
    'pypi': python_upload,
    'npm': npm_upload,
    'maven2': maven2_upload,
    'nuget': nuget_upload
}

CONFLICT_PATTERN = re.compile(
    r"conflict|already contains file|cannot publish over the previously published version",
    re.IGNORECASE
)
DELETED_PATTERN = re.compile(r"has been deleted", re.IGNORECASE)
ERROR_PATTERN = re.compile(r"error", re.IGNORECASE)
# config files written by this tool and leftovers of an interrupted download
IGNORED_FILES = {"settings.xml", ".npmrc", "nuget.config"}


class UploadModule:
    def __init__(self, artifact_metadata: ArtifactMetaData):
        self.artifact_metadata = artifact_metadata

    def upload(self) -> int:
        artifact_metadata = self.artifact_metadata
        if artifact_metadata.azure_password == "":
            print(
                "[red]variable azure_password/AZURE_PASSWORD [/red]"
                + " must be set for upload to work."
            )
            return 10
        if not artifact_metadata.directory.is_dir():
            print(f"[yellow]Nothing to upload, {artifact_metadata.directory} does not exist[/yellow]")
            return 0
        # a single pool for every format keeps the thread count at max_workers
        return sum_concurrently(self.upload_artifact, self.uploadable_packages(), artifact_metadata.max_workers)

    def uploadable_packages(self) -> Iterator[UploadablePackage]:
        artifact_metadata = self.artifact_metadata
        for repo_dir in artifact_metadata.directory.iterdir():
            if not (repo_dir.is_dir() and artifact_metadata.format_pattern.search(repo_dir.name)):
                continue
            for file_path in repo_dir.rglob('*'):
                if (file_path.name in IGNORED_FILES or file_path.suffix == ".part"
                        or not file_path.is_file()):
                    continue
                if path_matches_filter(str(file_path),
                        artifact_metadata.semver, artifact_metadata.version_pattern,
                        artifact_metadata.allow_invalid_version, artifact_metadata.name_pattern,
                        artifact_metadata.name_exclusion_pattern):
                    yield UploadablePackage(repo_format=repo_dir.name, artifact_path=str(file_path))

    def upload_artifact(self, uploadable_package: UploadablePackage) -> int:
        artifact_metadata = self.artifact_metadata
        artifact_path = uploadable_package.artifact_path

        upload_action = Upload_actions.get(uploadable_package.repo_format)
        if upload_action is None:
            print(f"[yellow]Skipping upload: {artifact_path} - format {uploadable_package.repo_format} is not supported[/yellow]")
            return 0

        # eg NUGET_REPOSITORY_URL
        repo_url_env_key = uploadable_package.repo_format.upper() + "_REPOSITORY_URL"
        env = os.environ.copy()
        if env.get(repo_url_env_key) is None:
            print(f"[red]Error[/red] Environment variable {repo_url_env_key} must be set to continue. Skipping...")
            return 2
        # the cli options may have been passed as arguments instead of environment variables
        env["AZURE_USERNAME"] = artifact_metadata.azure_username or env.get("AZURE_USERNAME", "")
        env["AZURE_PASSWORD"] = artifact_metadata.azure_password

        try:
            upload_command = upload_action(artifact_metadata, uploadable_package, env)
        except Exception as ex:
            print(f"[red]Error[/red] preparing the upload of {escape(artifact_path)} | {ex}")
            return 5
        if len(upload_command.commands) == 0:
            print(f"Skipping upload: [purple]{escape(artifact_path)}[/purple]"
                + " - File should not be uploaded or upload has been deferred"
            )
            return 0

        try:
            process = subprocess.run(
                upload_command.commands, env=upload_command.env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, errors="replace"
            )
        except OSError as ex:
            print(f"[yellow]Exception occurred trying to upload[/yellow] -> {escape(artifact_path)}")
            print(ex)
            print("If it's an executable issue, ensure that the binary used to run the command is valid.")
            print("eg. on windows, you may need to set --mvn-command 'mvn.cmd' instead of the default 'mvn'.")
            print("skipping...")
            return 3

        output = process.stdout or ""
        # printed in one go so the output of concurrent uploads does not interleave
        print(f"[bold]$ upload {escape(artifact_path)}[/bold]\n{escape(output.rstrip())}")

        if CONFLICT_PATTERN.search(output):
            print(
                f"[yellow]Conflict occurred when uploading: {escape(artifact_path)}[/yellow]"
                + " ignoring, renaming & skipping..."
            )
            os.replace(artifact_path, artifact_path + CustomExtenstion.remote_exists.value)
            return 0
        if DELETED_PATTERN.search(output):
            print(
                "[yellow]Package already deleted from remote registry and cannot be re-uploaded: "
                + f"{escape(artifact_path)}[/yellow] ignoring, renaming & skipping..."
            )
            os.replace(artifact_path, artifact_path + CustomExtenstion.remote_deleted.value)
            return 0
        if process.returncode == 0:
            if artifact_metadata.retain:
                os.replace(artifact_path, artifact_path + CustomExtenstion.uploaded.value)
            else:
                print("Deleting: " + escape(artifact_path))
                os.remove(artifact_path)
            print(f"[green]✔[/green] uploaded -> {escape(artifact_path)}")
            return 0

        print(f"[red]Upload failed ({process.returncode}): {escape(artifact_path)}[/red]")
        error_lines = [line for line in output.splitlines() if ERROR_PATTERN.search(line)]
        if error_lines:
            print(escape("\n".join(error_lines)))
        return 1
