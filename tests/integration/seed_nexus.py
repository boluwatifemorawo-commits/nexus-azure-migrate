'''
Seeds the docker compose Nexus with hosted pypi, npm, nuget and maven2
repositories containing a few small, generated packages.

    docker compose up -d --wait
    uv run python tests/integration/seed_nexus.py
'''
import base64, hashlib, io, json, os, sys, tarfile, time, zipfile

import requests

NEXUS_URL = os.environ.get("NEXUS_URL", "http://localhost:8081").rstrip("/")
AUTH = (os.environ.get("NEXUS_USERNAME", "admin"), os.environ.get("NEXUS_PASSWORD", "admin123"))
API = f"{NEXUS_URL}/service/rest/v1"
# prefix the names so they cannot clash with real packages in a test feed
PREFIX = os.environ.get("SEED_PREFIX", "nam-test")
VERSIONS = ["1.0.0", "1.1.0", "2.0.0"]

session = requests.Session()
session.auth = AUTH


def wait_for_nexus(timeout: int = 600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if session.get(f"{API}/status/writable", timeout=5).ok:
                return
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(5)
    sys.exit(f"Nexus at {NEXUS_URL} did not become writable")


def accept_eula():
    '''Nexus Community Edition (3.77+) rejects uploads until its EULA is accepted'''
    response = session.get(f"{API}/system/eula")
    if response.status_code == 404:  # older OSS releases have no EULA
        return
    eula = response.json()
    if eula.get("accepted"):
        return
    if os.environ.get("ACCEPT_NEXUS_EULA", "true").lower() != "true":
        sys.exit("Accept the Nexus EULA at " + NEXUS_URL + " or set ACCEPT_NEXUS_EULA=true")
    session.post(f"{API}/system/eula", json={"accepted": True, "disclaimer": eula["disclaimer"]}).raise_for_status()
    print("accepted the Nexus Community Edition EULA")


def create_hosted_repository(repo_format: str, name: str):
    if session.get(f"{API}/repositories/{name}").ok:
        return
    payload: dict = {
        "name": name, "online": True,
        "storage": {"blobStoreName": "default", "strictContentTypeValidation": True, "writePolicy": "allow_once"},
    }
    if repo_format == "maven":
        payload["maven"] = {"versionPolicy": "RELEASE", "layoutPolicy": "STRICT"}
    session.post(f"{API}/repositories/{repo_format}/hosted", json=payload).raise_for_status()
    print(f"created {repo_format} repository {name}")


def upload_component(repository: str, data: dict, files: dict):
    response = session.post(f"{API}/components", params={"repository": repository}, data=data, files=files)
    if response.status_code == 400 and "already" in response.text.lower():
        return
    response.raise_for_status()


def zip_bytes(entries: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def wheel(version: str) -> tuple[str, bytes]:
    package = PREFIX.replace("-", "_") + "_pkg"
    dist_info = f"{package}-{version}.dist-info"
    entries: dict[str, str | bytes] = {
        f"{package}/__init__.py": f'__version__ = "{version}"\n',
        f"{dist_info}/METADATA": f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\nSummary: test package\n",
        f"{dist_info}/WHEEL": "Wheel-Version: 1.0\nGenerator: seed\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = []
    for name, content in entries.items():
        raw = content.encode() if isinstance(content, str) else content
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(raw)}")
    record.append(f"{dist_info}/RECORD,,")
    entries[f"{dist_info}/RECORD"] = "\n".join(record) + "\n"
    return f"{package}-{version}-py3-none-any.whl", zip_bytes(entries)


def npm_tarball(name: str, version: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for file_name, content in {
            "package/package.json": json.dumps({"name": name, "version": version, "main": "index.js"}),
            "package/index.js": f"module.exports = '{version}';\n",
        }.items():
            raw = content.encode()
            info = tarfile.TarInfo(file_name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def nupkg(package_id: str, version: str) -> bytes:
    return zip_bytes({
        f"{package_id}.nuspec": f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <id>{package_id}</id><version>{version}</version><authors>seed</authors>
    <description>test package</description>
  </metadata>
</package>''',
        "lib/netstandard2.0/_._": "",
        "[Content_Types].xml": '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="nuspec" ContentType="application/octet" />
  <Default Extension="_" ContentType="application/octet" />
</Types>''',
    })


def maven_pom(group_id: str, artifact_id: str, version: str) -> bytes:
    return f'''<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>{group_id}</groupId><artifactId>{artifact_id}</artifactId><version>{version}</version>
  <packaging>jar</packaging>
</project>'''.encode()


def seed():
    wait_for_nexus()
    accept_eula()
    for repo_format in ("pypi", "npm", "nuget", "maven"):
        create_hosted_repository(repo_format, f"{repo_format}-hosted")

    npm_names = [f"{PREFIX}-hello", f"@{PREFIX}/scoped-hello"]
    nuget_id = "".join(part.capitalize() for part in PREFIX.split("-")) + ".Hello"
    group_id, artifact_id = f"com.example.{PREFIX.replace('-', '')}", "hello"
    for version in VERSIONS:
        file_name, content = wheel(version)
        upload_component("pypi-hosted", {}, {"pypi.asset": (file_name, content)})
        for name in npm_names:
            upload_component("npm-hosted", {}, {"npm.asset": (f"{name.split('/')[-1]}-{version}.tgz", npm_tarball(name, version))})
        upload_component("nuget-hosted", {}, {"nuget.asset": (f"{nuget_id}.{version}.nupkg", nupkg(nuget_id, version))})
        upload_component("maven-hosted", {
            "maven2.groupId": group_id, "maven2.artifactId": artifact_id, "maven2.version": version,
            "maven2.asset1.extension": "jar", "maven2.asset2.extension": "pom",
        }, {
            "maven2.asset1": (f"{artifact_id}-{version}.jar", zip_bytes({"META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n"})),
            "maven2.asset2": (f"{artifact_id}-{version}.pom", maven_pom(group_id, artifact_id, version)),
        })
        print(f"seeded version {version}")

    for repository in ("pypi-hosted", "npm-hosted", "nuget-hosted", "maven-hosted"):
        assets = session.get(f"{API}/assets", params={"repository": repository}).json()["items"]
        print(f"{repository}: {len(assets)} assets")


if __name__ == "__main__":
    seed()
