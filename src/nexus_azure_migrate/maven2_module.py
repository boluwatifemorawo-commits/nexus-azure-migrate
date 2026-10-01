import re
import xml.etree.ElementTree as ET
from pathlib import Path
from string import Template

from rich import print

from nexus_azure_migrate.common.models import ArtifactMetaData, UploadCommand, UploadablePackage
from nexus_azure_migrate.common.utils import command_prefix, create_config_file, extra_args, get_version_candidates

# maven expands ${env.X}, so no secret is written to disk
settings = '''
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0
                              https://maven.apache.org/xsd/settings-1.0.0.xsd">
    <servers>
        <server>
            <id>${env.MAVEN2_REPOSITORY_ID}</id>
            <username>${env.AZURE_USERNAME}</username>
            <password>${env.AZURE_PASSWORD}</password>
        </server>
    </servers>
</settings>
'''
pom_template = Template('''
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/maven-v4_0_0.xsd">

  <modelVersion>4.0.0</modelVersion>

  <groupId>$groupId</groupId>
  <artifactId>$artifactId</artifactId>
  <version>$version</version>
</project>
''')
SKIPPED_FILES_PATTERN = re.compile(r"(-javadoc|-sources)\.[a-z0-9]+$|\.(pom|md5|sha1|sha256|sha512|asc)$|maven-metadata\.xml")
REPOSITORY_ID = "azure_artifacts"


def maven2_upload(artifact_metadata: ArtifactMetaData, uploadable_artifact: UploadablePackage, env: dict[str, str]) -> UploadCommand:
    artifact_path = Path(uploadable_artifact.artifact_path)
    if SKIPPED_FILES_PATTERN.search(artifact_path.name):
        return UploadCommand(commands=[])

    env["MAVEN2_REPOSITORY_ID"] = REPOSITORY_ID
    settings_file = create_config_file(
        artifact_metadata.directory, uploadable_artifact,
        "settings.xml", settings
    )

    pom_file = next(artifact_path.parent.glob('*.pom'), None)
    if pom_file is None:
        if artifact_metadata.eager_upload:
            print(f"[yellow]POM file required for {artifact_path} not found. Deferring upload...[/yellow]")
            return UploadCommand(commands=[])
        pom_file = create_pom_file(artifact_path)
        if pom_file is None:
            return UploadCommand(commands=[])

    namespace = {'ns': env.get("MAVEN2_NAMESPACE") or "http://maven.apache.org/POM/4.0.0"}
    root = ET.parse(pom_file).getroot()

    def pom_value(tag: str) -> str:
        # groupId and version may be inherited from the parent pom
        element = root.find(f'ns:{tag}', namespace)
        if element is None:
            element = root.find(f'ns:parent/ns:{tag}', namespace)
        return (element.text or "").strip() if element is not None else ""

    group_id, artifact_id, version = pom_value('groupId'), pom_value('artifactId'), pom_value('version')
    if not (group_id and artifact_id and version):
        print(f"[red]Error[/red] POM file {pom_file} is missing ns:groupId/ns:artifactId/ns:version")
        return UploadCommand(commands=[])

    commands = command_prefix(artifact_metadata.mvn_command) + [
        "--batch-mode",
        "--settings", settings_file,
        "deploy:deploy-file",
        f"-DrepositoryId={REPOSITORY_ID}",
        f"-DgroupId={group_id}",
        f"-DartifactId={artifact_id}",
        f"-Dversion={version}",
        f"-Dpackaging={artifact_path.suffix.lstrip('.')}",
        f"-Dfile={artifact_path}",
        f"-Durl={env['MAVEN2_REPOSITORY_URL']}",
    ] + extra_args(env, 'MVN_EXTRA_ARGS')

    return UploadCommand(commands=commands, env=env)


def create_pom_file(artifact_path: Path) -> Path | None:
    '''
    Creates a minimal pom from the maven2 folder layout:
    maven2/<group/as/folders>/<artifactId>/<version>/<file>
    '''
    path_components = list(artifact_path.parts)
    format_index = len(path_components) - 1 - path_components[::-1].index("maven2")
    version_index = next(
        (
            idx for idx, component in enumerate(path_components)
            if idx > format_index + 1 and len(get_version_candidates(component)) > 0
        ), -1
    )
    if version_index == -1:
        print(
            f"[yellow]POM file required for {artifact_path} not found "
            + "and cannot be created due to non-semver versioning. Deferring upload...[/yellow]"
        )
        return None
    pom_file = artifact_path.with_suffix(".pom")
    pom_file.write_text(pom_template.substitute(
        groupId=".".join(path_components[(format_index + 1):(version_index - 1)]),
        artifactId=path_components[version_index - 1],
        version=path_components[version_index],
    ), encoding="utf-8")
    print(f"[blue]POM file created for {artifact_path}[/blue]")
    return pom_file
