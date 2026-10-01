import os, re
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from rich import print

from nexus_azure_migrate.common import common_callback
from nexus_azure_migrate.common.download_module import DownloadModule
from nexus_azure_migrate.common.upload_module import UploadModule
from nexus_azure_migrate.common.models import ArtifactMetaData, CLIAction, NexusConfig

app = typer.Typer(
    no_args_is_help=True,
    callback=common_callback,
    rich_markup_mode="markdown",
    pretty_exceptions_show_locals= os.environ.get('PRETTY_EXCEPTION') == '1'
)


@app.command()
def migrate(ctx: typer.Context,
            nexus_v2: Annotated[bool, typer.Option(
                "--nexus-v2",
                help="Specify that the nexus server is v2",
            )] = False,
            repo_format: Annotated[str, typer.Option(
                "--format", "-f",
                envvar="NEXUS_FORMAT",
                help="""
                Regex to specify desired repository formats.
                list of formats can be found at https://help.sonatype.com/en/formats.html
                """
            )] = ".*",
            repository: Annotated[str, typer.Option(
                "--repository", "-r",
                envvar="NEXUS_REPOSITORY",
                help="Regex to specify the desired repositories by name. Applied after --format"
            )] = ".*",
            directory: Annotated[Path, typer.Option(
                "--directory", "-d",
                envvar="NEXUS_DIRECTORY",
                help="The folder to store the artifacts in or upload the artifact from." \
                "For an upload, to work, the artifacts must be in a subfolder named after the --format. eg ./nexus-packages/maven2/..." \
                "This is automatically created during download.",
                file_okay=False,
                dir_okay=True
            )] = Path("./nexus-packages"),
            semver: Annotated[str, typer.Option(
                "--semver", "-s",
                envvar="NEXUS_SEMVAR",
                help="Semantic versioning rule to decide which versions should be selected."
            )] = ">=0.0.0",
            package_version: Annotated[str, typer.Option(
                "--package-version", "-v",
                envvar="NEXUS_PACKAGE_VERSION",
                help="Regex to decide which versions should be selected."
            )] = ".*",
            allow_invalid_version: Annotated[bool, typer.Option(
                help="This allows skipping the semver and package_version filter if the version is not a valid semver format."
            )] = False,
            artifact_name: Annotated[str, typer.Option(
                "--artifact-name", "-n",
                envvar="NEXUS_ARTIFACT_NAME",
                help="Regex to decide which files should be selected."
            )] = ".*",
            exclude_name: Annotated[str, typer.Option(
                envvar="NEXUS_EXCLUDE_NAME",
                help="Regex to decide which files should be ignored."
            )] = "exclude-nothing",
            actions: Annotated[List[CLIAction], typer.Option(
                "--actions", "-a",
                help="List of actions to be performed.",
                case_sensitive=False
            )] = [CLIAction.download, CLIAction.upload],
            retain: Annotated[bool, typer.Option(
                help="Retain artifacts in filesystem after successful upload. Useful if you plan to run this command multiple times.",
            )] = True,
            max_workers: Annotated[Optional[int], typer.Option(
                "--max-workers", "-w",
                envvar="MAX_WORKERS",
                help="Max number of threads to use in running this operation"
            )] = None,
            max_retry: Annotated[int, typer.Option(
                "--max-retry", "-x",
                envvar="MAX_RETRY",
                help="Max number of times to retry a failed artifact download"
            )] = 4,
            azure_username: Annotated[str, typer.Option(
                "--azure-username", "-u",
                envvar="AZURE_USERNAME",
                help="The username to use during upload to azure artifact"
            )] = "",
            azure_password: Annotated[str, typer.Option(
                "--azure-password", "-p",
                envvar=["AZURE_PASSWORD", "AZURE_DEVOPS_EXT_PAT"],
                help="The password to use during upload to azure artifact"
            )] = "",
            twine_command: Annotated[str, typer.Option(
                "--twine-command", "-t",
                envvar="TWINE_COMMAND",
                help="Specify the command to start twine. The first token must be executable"
            )] = "python -m twine",
            mvn_command: Annotated[str, typer.Option(
                "--mvn-command", "-m",
                envvar="MVN_COMMAND",
                help="Specify the command to start maven. The first token must be executable"
            )] = "mvn",
            npm_command: Annotated[str, typer.Option(
                envvar="NPM_COMMAND",
                help="Specify the command to start npm. The first token must be executable"
            )] = "npm",
            nuget_command: Annotated[str, typer.Option(
                envvar="NUGET_COMMAND",
                help="Specify the command to start nuget. The first token must be executable"
            )] = "dotnet nuget",
    ):
    """
    Migrate artifacts from chosen repositories. The options above must be specified before this command.
    It's a good idea to specify them as environment variables
    """
    version_pattern = re.compile(package_version)
    name_pattern = re.compile(artifact_name)
    name_exclusion_pattern = re.compile(exclude_name)
    format_pattern = re.compile(repo_format)
    repository_pattern = re.compile(repository)

    eager_upload = (
        CLIAction.download in actions
        and CLIAction.upload in actions
    )

    artifact_metadata = ArtifactMetaData(
        directory=directory,
        azure_username=azure_username,
        azure_password=azure_password,
        eager_upload=eager_upload,
        retain=retain,
        format_pattern=format_pattern,
        semver=semver,
        version_pattern=version_pattern,
        repository_pattern=repository_pattern,
        allow_invalid_version=allow_invalid_version,
        name_pattern=name_pattern,
        name_exclusion_pattern=name_exclusion_pattern,
        max_workers=max_workers,
        max_retry=max_retry,
        twine_command=twine_command,
        mvn_command=mvn_command,
        npm_command=npm_command,
        nuget_command=nuget_command
    )
    # ctx.obj is set by common_callback
    nexus_config: NexusConfig = ctx.obj
    if CLIAction.download in actions and not nexus_config.password:
        print("[red]No Nexus authentication method provided[/red]: set --nexus-password/NEXUS_PASSWORD or --nexus-config-path")
        raise typer.Exit(1)

    upload_module = UploadModule(artifact_metadata)
    download_module = DownloadModule(
        nexus_config, artifact_metadata,
        upload_module.upload_artifact
    )
    return_code = 0
    if CLIAction.download in actions:
        if nexus_v2:
            return_code += download_module.download_v2()
        else:
            return_code += download_module.download()
        print(
            "If no files were downloaded, then no artifact was found"
            + " that matched the given criteria"
        )
    if CLIAction.upload in actions:
        print("Beginning dedicated upload process...")
        # eager_upload should be false when the download process has ended
        artifact_metadata.eager_upload = False
        return_code += upload_module.upload()
        print(
            "If no file were uploaded, then no artifact was found"
            + " that matched the given criteria"
        )
    if return_code:
        print("[red]Some artifacts could not be migrated, see the errors above[/red]")
        raise typer.Exit(1)
