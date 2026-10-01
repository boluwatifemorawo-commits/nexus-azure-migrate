import os, subprocess, threading
from pathlib import Path

from rich import print

from nexus_azure_migrate.common.models import ArtifactMetaData, UploadCommand, UploadablePackage
from nexus_azure_migrate.common.utils import command_prefix, extra_args

nuget_config = '''<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
  </packageSources>
</configuration>
'''

_nuget_config_lock = threading.Lock()


def nuget_upload(artifact_metadata: ArtifactMetaData, uploadable_artifact: UploadablePackage, env: dict[str, str]) -> UploadCommand:
    nuget_file = artifact_metadata.directory / uploadable_artifact.repo_format / "nuget.config"
    nuget_source_name = env.get('NUGET_SOURCE_NAME') or 'azure-artifacts'
    # only the first upload thread creates the config, the others wait for it
    with _nuget_config_lock:
        if not nuget_file.exists():
            create_nuget_config(artifact_metadata.nuget_command, nuget_source_name, nuget_file, env)

    commands = command_prefix(artifact_metadata.nuget_command) + [
        "push",
        "--source", nuget_source_name,
        "--configfile", str(nuget_file),
        "--api-key", "irrelevant",
        uploadable_artifact.artifact_path
    ] + extra_args(env, 'NUGET_EXTRA_ARGS')

    return UploadCommand(commands=commands, env=env)


def create_nuget_config(
        nuget_command: str, nuget_source_name: str,
        nuget_file: Path, env: dict[str, str]):
    '''
    Creates a nuget.config containing only the azure artifacts source and its credentials
    '''
    nuget_file.parent.mkdir(parents=True, exist_ok=True)
    nuget_file.write_text(nuget_config, encoding="utf-8")
    commands = command_prefix(nuget_command) + [
        "add", "source", env['NUGET_REPOSITORY_URL'],
        "--name", nuget_source_name,
        "--username", env['AZURE_USERNAME'] or "azure",
        "--password", env['AZURE_PASSWORD'],
        "--configfile", str(nuget_file),
    ]
    if os.name != "nt":
        # password encryption is only supported on windows
        commands.append("--store-password-in-clear-text")
    result = subprocess.run(commands, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        nuget_file.unlink(missing_ok=True)
        print(result.stdout, result.stderr)
        raise RuntimeError(f"Could not add the nuget source {nuget_source_name}")
