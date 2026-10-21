# Contributing

Thanks for helping improve `nexus-azure-migrate`. This guide covers setup, testing, the pull request checks and releases.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.14+. [Task](https://taskfile.dev) and Docker are optional, for the local Nexus.

```sh
git clone https://github.com/boluwatifemorawo-commits/nexus-azure-migrate
cd nexus-azure-migrate
uv sync
uv run nexus-azure-migrate --help
```

## Making a change

1. Fork the repository and create a branch from `main`.
2. Make the change. Keep it focused on one thing.
3. Add or update tests in `tests/`.
4. Run the unit tests:

   ```sh
   uv run pytest
   ```

5. If you changed CLI options, regenerate the reference with `task generate-docs`.
6. If you changed CLI behaviour, update `README.md` and the agent skill in [plugins/nexus-azure-migrate/skills/nexus-azure-migrate/SKILL.md](./plugins/nexus-azure-migrate/skills/nexus-azure-migrate/SKILL.md).
7. Open a pull request against `main` and fill in the template.

## Testing against a local Nexus

[compose.yaml](./compose.yaml) runs Nexus 3, and `seed_nexus.py` fills it with small generated packages.

```sh
task nexus-up        # docker compose up + seed
NEXUS_URL=http://localhost:8081 NEXUS_PASSWORD=admin123 \
  uv run nexus-azure-migrate migrate -f '(pypi|npm|nuget|maven2)' -r hosted -a download
task nexus-down
```

For Nexus 2, run `docker compose --profile nexus2 up -d nexus2` and `uv run python tests/integration/seed_nexus2.py`.

To test uploads, use a throwaway Azure Artifacts feed. Never use a production feed: a deleted package version can never be published again.

## Pull request checks

Every pull request runs these workflows. All of them must pass before a merge.

| Workflow | What it checks |
| --- | --- |
| `CI / test` | Unit tests and the package build |
| `CI / plugins` | The Claude Code, Codex and Gemini CLI plugin manifests |
| `CI / integration` | A real download from a seeded Nexus 3 |
| `CI / docker` | The Docker image builds |
| `Security / trivy-repo` | Trivy scan of dependencies, secrets and misconfigurations. Fails on fixable HIGH or CRITICAL findings |
| `Security / trivy-image` | Trivy scan of the Docker image. Fails on fixable CRITICAL findings |
| `Security / codeql` | CodeQL analysis of the Python code and the workflows |
| `Security / zizmor` | Security lint of the GitHub Actions workflows |
| `Security / dependency-review` | Blocks new dependencies with high or critical vulnerabilities or GPL/AGPL licenses |

Findings also appear in the repository's **Security > Code scanning** tab.

To run Trivy locally before you push:

```sh
trivy fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --ignore-unfixed .
```

### Security rules for contributions

- Do not commit secrets, tokens, real Nexus or Azure URLs, or `.env` files. Use the placeholders in `.env.example`.
- Pin every GitHub Action to a full commit SHA, with the version in a comment: `uses: actions/checkout@<sha> # v5.1.0`.
- Give workflow jobs the smallest `permissions` they need.
- Report vulnerabilities privately, as described in [SECURITY.md](./SECURITY.md).

## AI agent plugin

The repository is also a plugin marketplace for AI coding agents. One skill in `plugins/nexus-azure-migrate/skills/` is shared by all of them:

| Agent | Manifest |
| --- | --- |
| Claude Code | `.claude-plugin/marketplace.json`, `plugins/nexus-azure-migrate/.claude-plugin/plugin.json` |
| Codex | `.agents/plugins/marketplace.json`, `plugins/nexus-azure-migrate/.codex-plugin/plugin.json` |
| Gemini CLI | `gemini-extension.json` |
| Any agent working in this repo | `AGENTS.md` (`CLAUDE.md` imports it) |

After you edit any of these, run `python .github/scripts/check_plugins.py`. To try the plugin locally:

```sh
claude --plugin-dir plugins/nexus-azure-migrate
codex plugin marketplace add . && codex plugin add nexus-azure-migrate@nexus-azure-migrate
gemini extensions link .
```

## Commit messages and releases

Every push to `main` publishes a release, and the commit message picks the version:

- No tag: an alpha of the next patch, on GitHub only.
- `#minor` or `#major`: bump that part instead of the patch.
- `#release`: a full release on GitHub and PyPI.

Only maintainers add `#release`. When you open a pull request, leave these tags out.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](./LICENSE).
