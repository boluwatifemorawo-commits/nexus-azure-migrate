# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, Gemini CLI, Copilot, Cursor and others) working in this repository.
Humans should read [CONTRIBUTING.md](./CONTRIBUTING.md), which covers the same ground in more detail.

## Project

`nexus-azure-migrate` is a Typer CLI that downloads hosted pypi, npm, nuget and maven2 packages from Sonatype Nexus 2 or 3 and publishes them to Azure Artifacts.

- `src/nexus_azure_migrate/__init__.py` defines the CLI (`migrate` command and its options).
- `src/nexus_azure_migrate/common/` has the Nexus 2/3 clients, the download and upload pipelines and shared models.
- `src/nexus_azure_migrate/<format>_module.py` holds the format-specific download paths and upload commands.
- `tests/` has unit tests. `tests/integration/` seeds a local Nexus from `compose.yaml`.
- `plugins/nexus-azure-migrate/` is the agent plugin (one shared skill) for Claude Code, Codex and Gemini CLI.

## Commands

```sh
uv sync                       # install, Python 3.14+
uv run pytest                 # unit tests, must pass before every commit
uv run nexus-azure-migrate --help
task generate-docs            # regenerate docs/GENERATED.md after changing CLI options
python .github/scripts/check_plugins.py   # after editing anything under plugins/ or the manifests
```

## Rules

- Never commit `.env`, tokens, passwords or real feed URLs. Use the placeholders from `.env.example`.
- Never run an upload (`-a upload` or the default actions) against a real Azure feed unless the user asks. Published versions cannot be re-published after deletion.
- Keep changes small and match the surrounding style. Add or update a test in `tests/` for behaviour changes.
- When CLI options or behaviour change, update `README.md`, `docs/GENERATED.md` and `plugins/nexus-azure-migrate/skills/nexus-azure-migrate/SKILL.md`.
- Pin every new GitHub Action to a full commit SHA with the version in a trailing comment.
- Commit messages control releases: `#release`, `#minor` and `#major` have meaning (see "Releasing" in `README.md`). Do not add them unless asked.
