# nexus-azure-migrate

A CLI that migrates hosted packages from Sonatype Nexus 2 or 3 to Azure Artifacts.
It supports `pypi`, `npm`, `nuget` and `maven2` repositories.

It downloads every artifact that matches your filters, then publishes it to an Azure Artifacts feed with the native tool for its format: `twine`, `npm`, `dotnet nuget` or `mvn`.
After each upload the local file is renamed with a marker extension, so you can safely re-run a migration.

Full CLI reference: [docs/GENERATED.md](./docs/GENERATED.md)

## Requirements

- Python 3.14+ (or Docker)
- The upload tool for each format you migrate. `twine` is installed with this package.
  - npm: `npm`
  - nuget: `dotnet` (`dotnet nuget`)
  - maven2: `mvn`
- A Nexus user that can read the repositories. Groovy scripts do **not** need to be enabled.
- An Azure DevOps personal access token with *Packaging (read & write)*.

## Installation

```sh
uv tool install git+https://github.com/<owner>/nexus-azure-migrate
# or
docker build -t nexus-azure-migrate .
```

## Configuration

Copy [.env.example](./.env.example) to `.env` and fill it in.
Set the `*_REPOSITORY_URL` for each format you migrate.

```shell
NEXUS_URL='https://nexus.example.com'
NEXUS_USERNAME='{username}'
NEXUS_PASSWORD='{password}'

AZURE_USERNAME='{username}'
AZURE_PASSWORD='{personal access token}'
# python
PYPI_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/pypi/upload/'
# maven
MAVEN2_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/maven/v1'
# npm - exclude https:// and /registry/
NPM_REPOSITORY_URL='pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/npm'
# nuget
NUGET_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/nuget/v3/index.json'
```

Leave out `{project}/` for organisation-scoped feeds. Use `%20` for spaces in a project name.

Other optional environment variables:

```shell
MAVEN2_NAMESPACE="http://maven.apache.org/POM/4.0.0"
NUGET_SOURCE_NAME="azure-artifacts"
# Extra arguments appended to the upload commands
MVN_EXTRA_ARGS=""
NPM_EXTRA_ARGS=""
NUGET_EXTRA_ARGS=""
TWINE_EXTRA_ARGS=""
PRETTY_EXCEPTION=1 # show local variables when an exception occurs (1 or 0)
```

## Examples

```shell
nexus-azure-migrate migrate -f pypi -n '\.whl$' -a download # download only the wheels from pypi repositories.

nexus-azure-migrate migrate -f '(pypi|npm|nuget|maven2)' # migrate all pypi, npm, nuget and maven2 packages.

nexus-azure-migrate migrate -f maven2 --semver '>=1.9.37' -n '\.(aar|pom)$' # migrate maven2 packages with a valid semver of at least 1.9.37.

nexus-azure-migrate migrate -f maven2 --semver '>1.9.37' -n '\.(apk|pom)$' -a upload # only upload maven2 packages already downloaded to ./nexus-packages/maven2.

nexus-azure-migrate migrate -f npm -n '.*auth.*' # migrate npm packages with "auth" in their name.

nexus-azure-migrate migrate -f nuget -n '.*CustomNugetArtifact.*' --semver '==0.0.1' # migrate version 0.0.1 of nuget packages with "CustomNugetArtifact" in the name.

nexus-azure-migrate migrate -f nuget --nexus-v2 --semver '==1.0.1' -r 'NuGet Releases' # migrate version 1.0.1 from a nexus 2 repository.

nexus-azure-migrate migrate -f maven2 --nexus-v2 -r 'my_registry' --allow-invalid-version -m mvnd --no-retain --exclude-name '\.apk$' # migrate everything except .apk files using mvnd, deleting each file once it is uploaded.

uv run --env-file .env nexus-azure-migrate migrate -f maven2 --nexus-v2 --allow-invalid-version -a download # load the environment variables from a .env file.

docker run --rm --env-file .env -v "$PWD/nexus-packages:/app/nexus-packages" nexus-azure-migrate migrate -f pypi # run the CLI from the Docker image.
```

> The Docker image only contains `twine`. To upload npm, nuget or maven packages, run the CLI where those tools are installed.

## How it works

- Downloads go to `--directory` (default `./nexus-packages`), in a sub folder per format, e.g. `./nexus-packages/maven2/...`.
  `-a upload` on its own uploads from the same layout.
- When both actions are selected, each artifact is uploaded as soon as it is downloaded.
  Anything that has to wait is picked up by a final upload pass, such as a maven jar whose pom has not been downloaded yet.
- After an upload, files are renamed with a marker extension and skipped from then on:
  - `.uploaded`: uploaded successfully.
  - `.remote_exists`: the feed already has that version.
  - `.remote_deleted`: the version was deleted from the feed and cannot be re-published.
- The exit code is `1` if any artifact failed, and `0` otherwise.

## Limitations

- Only hosted repositories can be migrated. Proxy and group repositories are not supported.
- The tool reads every asset name in each selected repository to apply the regex filters, which can take a while for large repositories.
  Nexus 2 folders whose version does not match `--semver`/`--package-version` are skipped without being read.
- If you change the Azure credentials for nuget after a migration, delete `<directory>/nuget/nuget.config`. Otherwise nuget keeps using the old credentials.
- maven2 folders must contain one pom, which belongs to the artifact in that folder. This is always true when the files were downloaded by this tool.
  If there is no pom, a minimal one is generated from the folder layout.
- maven2 artifacts are deployed with `deploy:deploy-file` and a generated pom, so dependency information in the original pom is not carried over.

## AI agent plugin

This repository is also a plugin for AI coding agents. It adds a `nexus-azure-migrate` skill that knows how to configure, filter, run and resume a migration.

```sh
# Claude Code
/plugin marketplace add boluwatifemorawo-commits/nexus-azure-migrate
/plugin install nexus-azure-migrate@nexus-azure-migrate

# Codex
codex plugin marketplace add boluwatifemorawo-commits/nexus-azure-migrate
codex plugin add nexus-azure-migrate@nexus-azure-migrate

# Gemini CLI
gemini extensions install https://github.com/boluwatifemorawo-commits/nexus-azure-migrate
```

Other agents (Copilot, Cursor and others) can read the skill directly from [plugins/nexus-azure-migrate/skills/nexus-azure-migrate/SKILL.md](./plugins/nexus-azure-migrate/skills/nexus-azure-migrate/SKILL.md).
Agents that work on this repository's code follow [AGENTS.md](./AGENTS.md).

## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full guide and the pull request checks, and [SECURITY.md](./SECURITY.md) to report a vulnerability.

```sh
uv sync
uv run pytest
```

### Testing against a local Nexus

[compose.yaml](./compose.yaml) runs a Nexus 3. `seed_nexus.py` creates hosted pypi, npm, nuget and maven2 repositories and fills them with small generated packages.
It also accepts the Nexus Community Edition EULA. Set `ACCEPT_NEXUS_EULA=false` to accept it yourself in the UI instead.

```sh
docker compose up -d --wait
uv run python tests/integration/seed_nexus.py

# Nexus 3 is at http://localhost:8081 (admin / admin123)
NEXUS_URL=http://localhost:8081 NEXUS_PASSWORD=admin123 \
  uv run nexus-azure-migrate migrate -f '(pypi|npm|nuget|maven2)' -r hosted -a download
```

To test `--nexus-v2`, start Nexus 2 with `docker compose --profile nexus2 up -d nexus2` and run `seed_nexus2.py`.
It is served at `http://localhost:8082/nexus`.

For the upload side, create a throwaway feed in an Azure DevOps project and point the `*_REPOSITORY_URL` variables at it.
An Entra access token works in place of a PAT: `az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798`.

To regenerate the CLI reference: `task generate-docs`.

### Releasing

Every push to `main` runs [release.yml](./.github/workflows/release.yml), which tags the commit and publishes a GitHub release with the wheel and sdist.
The commit message controls the version:

- Default: an alpha of the next patch, e.g. `v0.1.1-alpha.0` (`0.1.1a0` in Python), released on GitHub only as a pre-release.
- `#minor` or `#major`: bump that part instead of the patch.
- `#release`: a full release, e.g. `v0.1.1`, published to GitHub **and** PyPI.

```sh
git commit -m "add nuget retries #release"   # 0.1.1 on GitHub and PyPI
git commit -m "new npm filter #minor"         # 0.2.0a0 on GitHub only
```

The PyPI token is the `PYPI_API_TOKEN` repository secret.
