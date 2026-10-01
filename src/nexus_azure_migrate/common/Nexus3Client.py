from typing import Any, Iterator
from urllib.parse import urljoin

import requests

from nexus_azure_migrate.common.models import NexusConfig


class Nexus3Client:
    '''
    Minimal read-only client for the Nexus 3 REST API.
    Only uses public endpoints, so groovy scripts do not need to be enabled.
    '''
    def __init__(self, config: NexusConfig, session: requests.Session):
        self.base_url = urljoin(config.url, f"service/rest/{config.api_version}/")
        self.session = session

    def get(self, endpoint: str, **kwargs: Any) -> requests.Response:
        response = self.session.get(urljoin(self.base_url, endpoint.lstrip('/')), **kwargs)
        response.raise_for_status()
        return response

    def repositories_list(self) -> list[dict[str, Any]]:
        '''https://help.sonatype.com/en/repositories-api.html'''
        return self.get("repositories").json()

    def list_assets(self, repository: str) -> Iterator[dict[str, Any]]:
        '''
        Yields every asset in the repository, one page at a time.
        https://help.sonatype.com/en/assets-api.html
        '''
        params = {"repository": repository}
        while True:
            page = self.get("assets", params=params).json()
            yield from page.get("items", [])
            if not (token := page.get("continuationToken")):
                return
            params["continuationToken"] = token
