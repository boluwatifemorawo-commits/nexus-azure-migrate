'''
Seeds the docker compose Nexus 2 "releases" (maven2) repository.

    docker compose --profile nexus2 up -d nexus2
    uv run python tests/integration/seed_nexus2.py
'''
import os, sys, time

import requests

from seed_nexus import PREFIX, VERSIONS, maven_pom, zip_bytes

NEXUS_URL = os.environ.get("NEXUS2_URL", "http://localhost:8082/nexus").rstrip("/")
session = requests.Session()
session.auth = ("admin", "admin123")


def wait_for_nexus(timeout: int = 600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if session.get(f"{NEXUS_URL}/service/local/status", timeout=5).ok:
                return
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(5)
    sys.exit(f"Nexus 2 at {NEXUS_URL} did not start")


def seed():
    wait_for_nexus()
    group_id, artifact_id = f"com.example.{PREFIX.replace('-', '')}", "hello2"
    for version in VERSIONS:
        base = f"{NEXUS_URL}/content/repositories/releases/{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}"
        for extension, content in (
            ("jar", zip_bytes({"META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n"})),
            ("pom", maven_pom(group_id, artifact_id, version)),
        ):
            response = session.put(f"{base}.{extension}", data=content)
            if response.status_code != 400:  # 400: already deployed
                response.raise_for_status()
        print(f"seeded {group_id}:{artifact_id}:{version}")


if __name__ == "__main__":
    seed()
