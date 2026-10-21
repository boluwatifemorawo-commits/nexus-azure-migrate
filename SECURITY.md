# Security policy

## Supported versions

Only the latest release of `nexus-azure-migrate` receives security fixes.

## Reporting a vulnerability

Do **not** open a public issue for a vulnerability.

Report it privately through [GitHub security advisories](https://github.com/boluwatifemorawo-commits/nexus-azure-migrate/security/advisories/new).
Include the affected version, steps to reproduce and the impact.
You should get a reply within 7 days.

## Handling credentials

This tool handles Nexus passwords and Azure DevOps tokens.

- Pass them with environment variables or a `.env` file, never on the command line or in committed files.
- Use a personal access token with only the *Packaging (read & write)* scope, and set it to expire after the migration.
- `PRETTY_EXCEPTION=1` prints local variables in tracebacks, which can include credentials. Do not share that output.

## Automated checks

Every pull request runs:

- [Trivy](https://trivy.dev) on the repository (dependencies, secrets, misconfigurations) and on the Docker image.
- CodeQL for Python and GitHub Actions.
- zizmor for GitHub Actions workflow security.
- GitHub dependency review, which blocks new dependencies with high or critical vulnerabilities.
  A repository admin must enable the dependency graph and set the repository variable `DEPENDENCY_REVIEW_ENABLED=true`.

Dependabot keeps Python dependencies, GitHub Actions and the Docker base image up to date.
