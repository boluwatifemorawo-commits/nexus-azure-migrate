"""Checks the AI agent plugin manifests that no CLI validates on its own (codex),
and that every manifest points at the same plugin and skills."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
errors: list[str] = []


def load(path: str) -> dict:
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        errors.append(f"{path}: {e}")
        return {}


codex_market = load(".agents/plugins/marketplace.json")
claude_market = load(".claude-plugin/marketplace.json")
gemini = load("gemini-extension.json")

for entry in codex_market.get("plugins", []):
    plugin_dir = ROOT / entry["source"]["path"]
    manifest = load(str((plugin_dir / ".codex-plugin/plugin.json").relative_to(ROOT)))
    claude = load(str((plugin_dir / ".claude-plugin/plugin.json").relative_to(ROOT)))
    for name, value in {"codex": manifest.get("name"), "claude": claude.get("name")}.items():
        if value != entry["name"]:
            errors.append(f"{name} plugin name {value!r} does not match marketplace entry {entry['name']!r}")
    if manifest.get("version") != gemini.get("version"):
        errors.append(f"codex version {manifest.get('version')} != gemini version {gemini.get('version')}")

    skills_dir = plugin_dir / manifest.get("skills", "./skills/")
    skills = sorted(skills_dir.glob("*/SKILL.md"))
    if not skills:
        errors.append(f"no skills in {skills_dir}")
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not front:
            errors.append(f"{skill}: missing frontmatter")
            continue
        fields = dict(line.split(":", 1) for line in front[1].splitlines() if ":" in line)
        if fields.get("name", "").strip() != skill.parent.name:
            errors.append(f"{skill}: name must match its folder {skill.parent.name!r}")
        if not fields.get("description", "").strip():
            errors.append(f"{skill}: missing description")

claude_sources = {p["source"] for p in claude_market.get("plugins", [])}
codex_sources = {p["source"]["path"] for p in codex_market.get("plugins", [])}
if claude_sources != codex_sources:
    errors.append(f"claude marketplace sources {claude_sources} != codex sources {codex_sources}")

context = gemini.get("contextFileName")
if context and not (ROOT / context).is_file():
    errors.append(f"gemini contextFileName {context} does not exist")

print("\n".join(errors) or "plugin manifests ok")
sys.exit(1 if errors else 0)
