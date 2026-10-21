---
name: nexus-azure-migrate
description: Migrate hosted pypi, npm, nuget or maven2 packages from Sonatype Nexus 2 or 3 to an Azure Artifacts feed with the nexus-azure-migrate CLI. Use when the user wants to move, copy, download or re-publish packages from Nexus to Azure DevOps Artifacts, or asks how to filter, resume or debug such a migration.
---

# nexus-azure-migrate

`nexus-azure-migrate` downloads every artifact in a Nexus 2 or 3 hosted repository that matches the filters, then publishes each one to an Azure Artifacts feed with the native tool for its format.

| Format | Upload tool | Feed URL variable |
| --- | --- | --- |
| `pypi` | `twine` (installed with the CLI) | `PYPI_REPOSITORY_URL` |
| `npm` | `npm` | `NPM_REPOSITORY_URL` |
| `nuget` | `dotnet nuget` | `NUGET_REPOSITORY_URL` |
| `maven2` | `mvn` | `MAVEN2_REPOSITORY_URL` |

## 1. Install or locate the CLI

Check in this order and use the first one that works:

1. `nexus-azure-migrate --help` (already installed).
2. Inside a checkout of this repository: `uv run nexus-azure-migrate --help`.
3. Install it: `uv tool install nexus-azure-migrate` (or `pipx install nexus-azure-migrate`). Python 3.14+ is required.
4. Docker, pypi only: `docker run --rm --env-file .env -v "$PWD/nexus-packages:/app/nexus-packages" nexus-azure-migrate migrate ...`.

For npm, nuget and maven2 uploads, confirm the upload tool is on `PATH` before you start (`npm --version`, `dotnet nuget --version`, `mvn --version`).

## 2. Configure credentials

The CLI reads its configuration from environment variables. Prefer a `.env` file and run with `uv run --env-file .env ...`, or export the variables in the shell.

```shell
NEXUS_URL='https://nexus.example.com'
NEXUS_USERNAME='{username}'
NEXUS_PASSWORD='{password}'

AZURE_USERNAME='{username}'
AZURE_PASSWORD='{personal access token}'   # Packaging (read & write)
PYPI_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/pypi/upload/'
MAVEN2_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/maven/v1'
NPM_REPOSITORY_URL='pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/npm'   # no https:// and no /registry/
NUGET_REPOSITORY_URL='https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/nuget/v3/index.json'
```

- Leave out `{project}/` for organisation-scoped feeds. Use `%20` for spaces in a project name.
- Only set the `*_REPOSITORY_URL` for the formats being migrated.
- Never print, log or commit the values of `NEXUS_PASSWORD` or `AZURE_PASSWORD`. Do not put secrets on the command line when an environment variable works.
- An Entra token can replace the PAT: `az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798`.

## 3. Plan the migration

Global options (`--nexus-url`, `--nexus-username`, ...) go **before** `migrate`. Everything else goes after it.

Key `migrate` options:

- `-f/--format` regex over repository formats, e.g. `'(pypi|npm)'`.
- `-r/--repository` regex over repository names.
- `--nexus-v2` when the server is Nexus 2.
- `-n/--artifact-name` and `--exclude-name` regexes over file names.
- `-s/--semver` (e.g. `'>=1.2.0'`, `'==0.0.1'`) and `-v/--package-version` regex to filter versions. Add `--allow-invalid-version` to keep versions that are not valid semver.
- `-a/--actions` `download`, `upload` or both (default both).
- `-d/--directory` working folder, default `./nexus-packages/<format>/...`.
- `--no-retain` deletes each local file after a successful upload.
- `-w/--max-workers`, `-x/--max-retry`.

Run `nexus-azure-migrate migrate --help` for the full list.

Recommended flow for a real migration:

1. **Dry run the selection** with `-a download` into a scratch directory. Check what was downloaded before uploading anything.
2. **Upload** with `-a upload` against the same `--directory`, or run both actions once the filters are right.
3. **Re-run safely.** After each upload the local file is renamed with a marker and skipped from then on:
   - `.uploaded` uploaded successfully.
   - `.remote_exists` the feed already has that version.
   - `.remote_deleted` the version was deleted from the feed and cannot be re-published.

Ask the user before running any upload, because publishing to a feed cannot be undone (a deleted version can never be re-published).

## 4. Examples

```shell
# download only the wheels from pypi repositories
nexus-azure-migrate migrate -f pypi -n '\.whl$' -a download

# migrate all supported formats
nexus-azure-migrate migrate -f '(pypi|npm|nuget|maven2)'

# maven2 packages with a semver of at least 1.9.37
nexus-azure-migrate migrate -f maven2 --semver '>=1.9.37' -n '\.(aar|pom)$'

# version 1.0.1 from a Nexus 2 nuget repository
nexus-azure-migrate migrate -f nuget --nexus-v2 --semver '==1.0.1' -r 'NuGet Releases'
```

## 5. Troubleshooting

- Exit code `1` means at least one artifact failed. Read the summary, fix the cause and re-run; finished files are skipped.
- Only hosted repositories are supported. Proxy and group repositories are not.
- If nuget credentials changed after a migration, delete `<directory>/nuget/nuget.config`.
- maven2 folders need exactly one pom. If none exists, a minimal pom is generated from the folder layout. Dependency information in the original pom is not carried over.
- `PRETTY_EXCEPTION=1` shows local variables in tracebacks. It can print secrets, so do not share that output.
