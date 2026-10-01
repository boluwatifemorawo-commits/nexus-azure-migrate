import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from re import Pattern
from typing import Any, Iterable


@dataclass
class NexusConfig:
    '''Connection settings for a Nexus 2/3 server'''
    url: str = "http://localhost:8081"
    username: str = "admin"
    password: str = ""
    x509_verify: bool = True
    api_version: str = "v1"

    def __post_init__(self):
        self.url = self.url.rstrip('/') + '/'

    @property
    def auth(self) -> tuple[str, str] | None:
        return (self.username, self.password) if self.username and self.password else None

    @classmethod
    def from_file(cls, config_path: Path) -> "NexusConfig":
        '''
        Loads a json config file. Accepts both the keys written by `nexus3 login`
        (url, username, password, x509_verify, api_version) and the legacy
        nexus_url, nexus_user, nexus_pass, nexus_verify keys.
        '''
        data: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
        defaults = cls()
        return cls(
            url=data.get("url", data.get("nexus_url", defaults.url)),
            username=data.get("username", data.get("nexus_user", defaults.username)),
            password=data.get("password", data.get("nexus_pass", defaults.password)),
            x509_verify=data.get("x509_verify", data.get("nexus_verify", defaults.x509_verify)),
            api_version=data.get("api_version", defaults.api_version),
        )


@dataclass
class ArtifactMetaData:
    directory: Path
    azure_username: str
    azure_password: str
    eager_upload: bool
    retain: bool
    format_pattern: Pattern[str]
    semver: str
    version_pattern: Pattern[str]
    repository_pattern: Pattern[str]
    allow_invalid_version: bool
    name_pattern: Pattern[str]
    name_exclusion_pattern: Pattern[str]
    max_workers: int | None
    twine_command: str
    mvn_command: str
    npm_command: str
    nuget_command: str
    max_retry: int


@dataclass
class DownloadablePackage:
    nexus_config: NexusConfig
    package_metadata: dict[str, str]


@dataclass
class UploadableArtifact:
    '''
    Contains metadata about an artifact which may contain one or multiple packages
    '''
    repo_format: str
    artifact_paths: Iterable[str]


@dataclass
class UploadablePackage:
    repo_format: str
    artifact_path: str


@dataclass
class UploadCommand:
    commands: list[str]
    env: dict[str, str] = field(default_factory=dict)


class CLIAction(str, Enum):
    download = "download"
    upload = "upload"


class CustomExtenstion(str, Enum):
    uploaded = ".uploaded"
    remote_exists = ".remote_exists"
    remote_deleted = ".remote_deleted"
    pattern = r"\.(uploaded|remote_exists|remote_deleted)$"
