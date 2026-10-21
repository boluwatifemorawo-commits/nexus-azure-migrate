## What and why

<!-- What does this change and why is it needed? Link the issue if there is one. -->

## How it was tested

- [ ] `uv run pytest`
- [ ] Ran the CLI against a local Nexus (`task nexus-up`) if download or upload code changed
- [ ] `task generate-docs` if CLI options changed

## Checklist

- [ ] No secrets, tokens or real feed URLs in the diff, logs or test data
- [ ] New GitHub Actions are pinned to a full commit SHA
- [ ] The skill in `plugins/nexus-azure-migrate/skills/` is updated if CLI behaviour changed
