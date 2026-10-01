# `nexus-azure-migrate`

Nexus Azure Migration Tool enables the migration of nexus2/3 artifacts to azure artifacts.

**Usage**:

```console
$ nexus-azure-migrate [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--nexus-config-path <file>`: json file containing url, username, password, x509_verify (or nexus_url, nexus_user, nexus_pass, nexus_verify)  [env var: NEXUS_CONFIG_FILE]
* `--nexus-username <str>`: Nexus user with sufficient read permissions, specify this if nexus-config-path is not present  [env var: NEXUS_USERNAME; default: admin]
* `--nexus-password <str>`: password for user, specify this if nexus-config-path is not present  [env var: NEXUS_PASSWORD]
* `--nexus-url <str>`: URL to Nexus 3 OSS service, specify this if nexus-config-path is not present  [env var: NEXUS_URL; default: http://localhost:8081]
* `--nexus-x509-verify / --no-nexus-x509-verify`: toggle certificate validation, optionally specify this if nexus-config-path is not present  [default: nexus-x509-verify]
* `--nexus-api-version <str>`: Nexus REST API version to be used, optionally specify this if nexus-config-path is not present  [env var: NEXUS_API_VERSION; default: v1]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `migrate`: Migrate artifacts from chosen repositories.

## `nexus-azure-migrate migrate`

Migrate artifacts from chosen repositories. The options above must be specified before this command.
It's a good idea to specify them as environment variables

**Usage**:

```console
$ nexus-azure-migrate migrate [OPTIONS]
```

**Options**:

* `--nexus-v2`: Specify that the nexus server is v2
* `-f, --format <str>`: Regex to specify desired repository formats.
list of formats can be found at https://help.sonatype.com/en/formats.html  [env var: NEXUS_FORMAT; default: .*]
* `-r, --repository <str>`: Regex to specify the desired repositories by name. Applied after --format  [env var: NEXUS_REPOSITORY; default: .*]
* `-d, --directory <directory>`: The folder to store the artifacts in or upload the artifact from.For an upload, to work, the artifacts must be in a subfolder named after the --format. eg ./nexus-packages/maven2/...This is automatically created during download.  [env var: NEXUS_DIRECTORY; default: nexus-packages]
* `-s, --semver <str>`: Semantic versioning rule to decide which versions should be selected.  [env var: NEXUS_SEMVAR; default: >=0.0.0]
* `-v, --package-version <str>`: Regex to decide which versions should be selected.  [env var: NEXUS_PACKAGE_VERSION; default: .*]
* `--allow-invalid-version / --no-allow-invalid-version`: This allows skipping the semver and package_version filter if the version is not a valid semver format.  [default: no-allow-invalid-version]
* `-n, --artifact-name <str>`: Regex to decide which files should be selected.  [env var: NEXUS_ARTIFACT_NAME; default: .*]
* `--exclude-name <str>`: Regex to decide which files should be ignored.  [env var: NEXUS_EXCLUDE_NAME; default: exclude-nothing]
* `-a, --actions <download|upload>`: List of actions to be performed.  [default: download, upload]
* `--retain / --no-retain`: Retain artifacts in filesystem after successful upload. Useful if you plan to run this command multiple times.  [default: retain]
* `-w, --max-workers <int>`: Max number of threads to use in running this operation  [env var: MAX_WORKERS]
* `-x, --max-retry <int>`: Max number of times to retry a failed artifact download  [env var: MAX_RETRY; default: 4]
* `-u, --azure-username <str>`: The username to use during upload to azure artifact  [env var: AZURE_USERNAME]
* `-p, --azure-password <str>`: The password to use during upload to azure artifact  [env var: AZURE_PASSWORD, AZURE_DEVOPS_EXT_PAT]
* `-t, --twine-command <str>`: Specify the command to start twine. The first token must be executable  [env var: TWINE_COMMAND; default: python -m twine]
* `-m, --mvn-command <str>`: Specify the command to start maven. The first token must be executable  [env var: MVN_COMMAND; default: mvn]
* `--npm-command <str>`: Specify the command to start npm. The first token must be executable  [env var: NPM_COMMAND; default: npm]
* `--nuget-command <str>`: Specify the command to start nuget. The first token must be executable  [env var: NUGET_COMMAND; default: dotnet nuget]
* `--help`: Show this message and exit.
