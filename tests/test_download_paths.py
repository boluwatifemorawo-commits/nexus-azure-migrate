import re
from pathlib import Path

import pytest

from nexus_azure_migrate.common.download_module import DownloadModule
from nexus_azure_migrate.common.models import ArtifactMetaData, DownloadablePackage, NexusConfig


@pytest.fixture
def module(tmp_path: Path) -> DownloadModule:
    metadata = ArtifactMetaData(
        directory=tmp_path, azure_username="", azure_password="", eager_upload=False, retain=True,
        format_pattern=re.compile(".*"), semver=">=0.0.0", version_pattern=re.compile(".*"),
        repository_pattern=re.compile(".*"), allow_invalid_version=False, name_pattern=re.compile(".*"),
        name_exclusion_pattern=re.compile("exclude-nothing"), max_workers=1, twine_command="",
        mvn_command="", npm_command="", nuget_command="", max_retry=0,
    )
    module = DownloadModule(NexusConfig(), metadata, lambda _: 0)
    module.written: list[Path] = []
    module.download_file = lambda url, destination: module.written.append(destination)
    return module


@pytest.mark.parametrize("repo_format, nexus_path, expected", [
    # nexus3 paths start with a slash, which must not make the destination absolute
    ("pypi", "/packages/pkg/1.0.0/pkg-1.0.0.whl", "pypi/packages/pkg/1.0.0/pkg-1.0.0.whl"),
    ("npm", "@scope/pkg/-/pkg-1.0.0.tgz", "npm/scope/pkg/pkg-1.0.0.tgz"),
    ("nuget", "Some.Package/1.0.0", "nuget/Some.Package/1.0.0/Some.Package.1.0.0.nupkg"),
])
def test_destination(module: DownloadModule, tmp_path: Path, repo_format: str, nexus_path: str, expected: str):
    package = DownloadablePackage(NexusConfig(), {"path": nexus_path, "format": repo_format, "downloadUrl": "x"})
    assert module.download_package(package) == 0
    assert module.written == [tmp_path / expected]


def test_paths_cannot_escape_the_directory(module: DownloadModule):
    package = DownloadablePackage(NexusConfig(), {"path": "../../evil-1.0.0.whl", "format": "pypi", "downloadUrl": "x"})
    assert module.download_package(package) == 1
    assert module.written == []
