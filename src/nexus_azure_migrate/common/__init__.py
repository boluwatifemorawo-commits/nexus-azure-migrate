from pathlib import Path
from typing import Annotated, Optional

import typer

from nexus_azure_migrate.common.models import NexusConfig

nexus_help_panel = "Nexus Authentication"
nexus_default = NexusConfig()


def common_callback(ctx: typer.Context,
        nexus_config_path: Annotated[Optional[Path], typer.Option(
            envvar="NEXUS_CONFIG_FILE",
            help="json file containing url, username, password, x509_verify (or nexus_url, nexus_user, nexus_pass, nexus_verify)",
            rich_help_panel=nexus_help_panel,
            exists=True, dir_okay=False,
        )] = None,
        nexus_username: Annotated[str, typer.Option(
            envvar="NEXUS_USERNAME",
            help="Nexus user with sufficient read permissions, specify this if nexus-config-path is not present",
            rich_help_panel=nexus_help_panel
        )] = nexus_default.username,
        nexus_password: Annotated[str, typer.Option(
            envvar="NEXUS_PASSWORD",
            help="password for user, specify this if nexus-config-path is not present",
            rich_help_panel=nexus_help_panel
        )] = nexus_default.password,
        nexus_url: Annotated[str, typer.Option(
            envvar="NEXUS_URL",
            help="URL to Nexus 3 OSS service, specify this if nexus-config-path is not present",
            rich_help_panel=nexus_help_panel
        )] = "http://localhost:8081",
        nexus_x509_verify: Annotated[bool, typer.Option(
            help="toggle certificate validation, optionally specify this if nexus-config-path is not present",
            rich_help_panel=nexus_help_panel
        )] = nexus_default.x509_verify,
        nexus_api_version: Annotated[str, typer.Option(
            envvar="NEXUS_API_VERSION",
            help="Nexus REST API version to be used, optionally specify this if nexus-config-path is not present",
            rich_help_panel=nexus_help_panel
        )] = nexus_default.api_version,
        nexus_groovy_enabled: Annotated[bool, typer.Option(
            help="Deprecated and ignored. Groovy scripts are no longer required.",
            rich_help_panel=nexus_help_panel,
            hidden=True
        )] = True,
    ):
    """
    Nexus Azure Migration Tool enables the migration of nexus2/3 artifacts to azure artifacts.
    """
    if nexus_config_path is not None:
        ctx.obj = NexusConfig.from_file(nexus_config_path)
        return
    ctx.obj = NexusConfig(
        username=nexus_username, password=nexus_password, url=nexus_url,
        x509_verify=nexus_x509_verify, api_version=nexus_api_version,
    )
