import re
from pathlib import Path

import pytest

from nexus_azure_migrate.common.models import ArtifactMetaData, UploadablePackage
from nexus_azure_migrate.maven2_module import maven2_upload
from nexus_azure_migrate.npm_module import npm_upload
from nexus_azure_migrate.pypi_module import python_upload


@pytest.fixture
def metadata(tmp_path: Path) -> ArtifactMetaData:
    return ArtifactMetaData(
        directory=tmp_path / "POC Project 1", azure_username="user", azure_password="secret",
        eager_upload=False, retain=True, format_pattern=re.compile(".*"), semver=">=0.0.0",
        version_pattern=re.compile(".*"), repository_pattern=re.compile(".*"),
        allow_invalid_version=False, name_pattern=re.compile(".*"),
        name_exclusion_pattern=re.compile("exclude-nothing"), max_workers=2,
        twine_command="python -m twine", mvn_command="mvn", npm_command="npm",
        nuget_command="dotnet nuget", max_retry=1,
    )


def env() -> dict[str, str]:
    return {
        "AZURE_USERNAME": "user", "AZURE_PASSWORD": "secret",
        "PYPI_REPOSITORY_URL": "https://pypi", "NPM_REPOSITORY_URL": "npm",
        "MAVEN2_REPOSITORY_URL": "https://maven", "TWINE_EXTRA_ARGS": "--verbose --skip-existing",
    }


def test_paths_with_spaces_stay_one_argument(metadata: ArtifactMetaData):
    path = str(metadata.directory / "pypi" / "pkg-1.0.0.whl")
    command = python_upload(metadata, UploadablePackage("pypi", path), env())
    assert path in command.commands
    assert command.commands[-2:] == ["--verbose", "--skip-existing"]
    assert command.env["TWINE_PASSWORD"] == "secret"


def test_npmrc_does_not_contain_the_secret(metadata: ArtifactMetaData):
    path = str(metadata.directory / "npm" / "pkg" / "pkg-1.0.0.tgz")
    command = npm_upload(metadata, UploadablePackage("npm", path), env())
    npmrc = Path(command.commands[command.commands.index("--userconfig") + 1])
    assert "secret" not in npmrc.read_text()
    assert command.commands[-1] == path


def maven_dir(metadata: ArtifactMetaData) -> Path:
    directory = metadata.directory / "maven2" / "com" / "example" / "lib" / "1.2.3"
    directory.mkdir(parents=True)
    return directory


def test_maven_uses_the_pom(metadata: ArtifactMetaData):
    directory = maven_dir(metadata)
    (directory / "lib-1.2.3.pom").write_text("""<project xmlns="http://maven.apache.org/POM/4.0.0">
        <parent><groupId>com.example</groupId><artifactId>parent</artifactId><version>1.2.3</version></parent>
        <artifactId>lib</artifactId></project>""")
    jar = directory / "lib-1.2.3.jar"
    jar.write_text("")
    commands = maven2_upload(metadata, UploadablePackage("maven2", str(jar)), env()).commands
    # groupId and version are inherited from the parent
    assert "-DgroupId=com.example" in commands
    assert "-Dversion=1.2.3" in commands
    assert "-Dpackaging=jar" in commands
    assert f"-Dfile={jar}" in commands


def test_maven_generates_a_missing_pom(metadata: ArtifactMetaData):
    jar = maven_dir(metadata) / "lib-1.2.3.jar"
    jar.write_text("")
    commands = maven2_upload(metadata, UploadablePackage("maven2", str(jar)), env()).commands
    assert jar.with_suffix(".pom").exists()
    assert "-DgroupId=com.example" in commands
    assert "-DartifactId=lib" in commands


@pytest.mark.parametrize("name", ["lib-1.2.3.pom", "lib-1.2.3-sources.jar", "lib-1.2.3.jar.sha1"])
def test_maven_skips_side_files(metadata: ArtifactMetaData, name: str):
    path = maven_dir(metadata) / name
    assert maven2_upload(metadata, UploadablePackage("maven2", str(path)), env()).commands == []


def test_pypi_skips_metadata_files(metadata: ArtifactMetaData):
    path = str(metadata.directory / "pypi" / "pkg-1.0.0-py3-none-any.whl.metadata")
    assert python_upload(metadata, UploadablePackage("pypi", path), env()).commands == []
