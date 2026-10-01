from nexus_azure_migrate.common.models import ArtifactMetaData, UploadCommand, UploadablePackage
from nexus_azure_migrate.common.utils import command_prefix, create_config_file, extra_args

# npm expands ${VAR} from the environment, so no secret is written to disk
npmrc = '''
registry=https://${NPM_REPOSITORY_URL}/registry/

; begin auth token
//${NPM_REPOSITORY_URL}/registry/:_authToken=${AZURE_PASSWORD}
; end auth token
'''


def npm_upload(artifact_metadata: ArtifactMetaData, uploadable_artifact: UploadablePackage, env: dict[str, str]) -> UploadCommand:
    npmrc_file = create_config_file(
        artifact_metadata.directory, uploadable_artifact,
        ".npmrc", npmrc
    )
    commands = command_prefix(artifact_metadata.npm_command) + [
        "--userconfig", npmrc_file, "publish",
        "--tag", "migrated",
        uploadable_artifact.artifact_path
    ] + extra_args(env, 'NPM_EXTRA_ARGS')

    return UploadCommand(commands=commands, env=env)
