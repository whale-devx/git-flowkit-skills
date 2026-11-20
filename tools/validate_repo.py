"""Offline structural checks for the skill, documentation, JSON and workflow pins."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/git-flowkit"
sys.path.insert(0, str(SKILL / "scripts"))
from flowkit_core import FlowkitError, load_config, load_json, read_text, validate_schema
from flowkit_release import parse_version


def validate() -> list[str]:
    checked = []
    text = read_text(SKILL / "SKILL.md")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise FlowkitError("SKILL.md requires YAML frontmatter")
    front = text.split("---\n", 2)[1]
    fields = dict(re.findall(r"^([a-z-]+): (.+)$", front, re.MULTILINE))
    if fields.get("name") != SKILL.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]):
        raise FlowkitError("Invalid skill name or directory mismatch")
    if not 1 <= len(fields.get("description", "")) <= 1024:
        raise FlowkitError("Skill description length is invalid")
    if len(fields.get("compatibility", "")) > 500:
        raise FlowkitError("Skill compatibility exceeds 500 characters")
    if not (SKILL / "LICENSE.txt").is_file():
        raise FlowkitError("The installable skill must carry its license")
    schema = load_json(SKILL / "assets/config.schema.json")
    validate_schema(load_json(SKILL / "assets/defaults.json"), schema)
    validate_schema(load_json(ROOT / "examples/team-config.json"), schema)
    load_config(ROOT)
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix == ".json":
            load_json(path)
        if path.suffix == ".py":
            ast.parse(read_text(path), filename=str(path))
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^\s)]+)\)", read_text(path)):
                if ":" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                if not (path.parent / target).resolve().is_file():
                    raise FlowkitError(f"Broken local link in {path.relative_to(ROOT)}: {target}")
        if path.suffix in (".yml", ".yaml"):
            content = read_text(path)
            for action in re.findall(r"uses:\s*([^\s#]+)", content):
                if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action):
                    raise FlowkitError(f"Action is not SHA-pinned: {action}")
            if "pull_request_target:" in content:
                raise FlowkitError("Privileged PR triggers are not permitted in this implementation")
        checked.append(path.relative_to(ROOT).as_posix())
    manifest = load_json(ROOT / ".release-please-manifest.json")
    if manifest.get(".") != read_text(ROOT / "version.txt").strip():
        raise FlowkitError("Root manifest and version.txt disagree")
    parse_version(manifest["."])
    return checked


if __name__ == "__main__":
    try:
        checked = validate()
        print(f"Validated {len(checked)} source files, skill metadata, JSON, local links, and action pins.")
    except (FlowkitError, SyntaxError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
