import re

from nexus_azure_migrate.common.models import ArtifactMetaData, UploadCommand, UploadablePackage
from nexus_azure_migrate.common.utils import command_prefix, extra_args


# anything else, such as the PEP 658 .whl.metadata files nexus serves, is not a distribution
DISTRIBUTION_PATTERN = re.compile(r"\.(whl|tar\.gz|zip|egg|tar\.bz2)$")


def python_upload(artifact_metadata: ArtifactMetaData, uploadable_package: UploadablePackage, env: dict[str, str]) -> UploadCommand:
    if not DISTRIBUTION_PATTERN.search(uploadable_package.artifact_path):
        return UploadCommand(commands=[])
    commands = command_prefix(artifact_metadata.twine_command) + [
        "upload", "--non-interactive", uploadable_package.artifact_path
    ] + extra_args(env, 'TWINE_EXTRA_ARGS')

    # use case of where prefix does not match the format
    env['TWINE_USERNAME'] = env['AZURE_USERNAME']
    env['TWINE_PASSWORD'] = env['AZURE_PASSWORD']
    env['TWINE_REPOSITORY_URL'] = env['PYPI_REPOSITORY_URL']

    return UploadCommand(commands=commands, env=env)
