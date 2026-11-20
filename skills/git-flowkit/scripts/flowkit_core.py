"""Git FlowKit's offline policy helpers. Python 3.11+, standard library only."""
from __future__ import annotations

import copy
import json
import os
import re
import string
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CONFIG_NAME = ".git-flowkit.json"
MAX_BYTES = 1_048_576
KINDS = ("commit", "pr", "merge", "release")


class FlowkitError(ValueError):
    """An actionable validation failure, not a Python traceback."""


def read_text(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise FlowkitError(f"File exceeds 1 MiB: {path}")
        return data.decode("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as exc:
        raise FlowkitError(f"Cannot read UTF-8 file {path}: {exc}") from exc


def load_json(path: Path) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise FlowkitError(f"Duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise FlowkitError(f"Non-finite JSON number {value} in {path}")

    try:
        return json.loads(read_text(path), object_pairs_hook=unique, parse_constant=invalid)
    except json.JSONDecodeError as exc:
        raise FlowkitError(f"Invalid JSON in {path}: {exc}") from exc


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def validate_schema(value: Any, schema: dict[str, Any], where: str = "config") -> None:
    """Validate the deliberately small JSON Schema subset used by our bundled schema."""
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int}
    kind = schema.get("type")
    if kind and (not isinstance(value, types[kind]) or (kind == "integer" and isinstance(value, bool))):
        raise FlowkitError(f"{where}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise FlowkitError(f"{where}: expected one of {schema['enum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise FlowkitError(f"{where}: missing {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            rule = properties.get(key, schema.get("additionalProperties", True))
            if rule is False:
                raise FlowkitError(f"{where}: unknown key {key}")
            if isinstance(rule, dict):
                validate_schema(item, rule, f"{where}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise FlowkitError(f"{where}: too few items")
        if schema.get("uniqueItems") and len({json_text(x) for x in value}) != len(value):
            raise FlowkitError(f"{where}: duplicate items")
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), f"{where}[{index}]")
    if isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", MAX_BYTES):
            raise FlowkitError(f"{where}: invalid length")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value, re.ASCII):
            raise FlowkitError(f"{where}: invalid format")
    if isinstance(value, int) and not isinstance(value, bool):
        if not schema.get("minimum", value) <= value <= schema.get("maximum", value):
            raise FlowkitError(f"{where}: out of range")


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def safe_path(root: Path, relative: str) -> Path:
    """Do not let configuration or templates reach outside their owning directory."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or any(part.lower() == ".git" for part in rel.parts) or "\\" in relative or ":" in relative or any(ord(c) < 32 for c in relative):
        raise FlowkitError(f"Unsafe relative path: {relative}")
    base = root.resolve()
    candidate = base / rel
    if not candidate.resolve().is_relative_to(base):
        raise FlowkitError(f"Path escapes its owning directory: {relative}")
    return candidate


def global_path() -> Path:
    if os.environ.get("GIT_FLOWKIT_CONFIG"):
        return Path(os.environ["GIT_FLOWKIT_CONFIG"]).expanduser()
    default = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) if os.name == "nt" else Path.home() / ".config"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(default))) / "git-flowkit" / "config.json"


def load_config(root: Path) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    schema = load_json(ASSETS / "config.schema.json")
    config = load_json(ASSETS / "defaults.json")
    layers: list[tuple[Path, dict[str, Any]]] = []
    paths = [] if os.environ.get("GIT_FLOWKIT_NO_GLOBAL") == "1" else [global_path()]
    paths.append(safe_path(root, CONFIG_NAME))
    for path in paths:
        if path.exists() or path.is_symlink():
            layer = load_json(path)
            validate_schema(layer, schema, str(path))
            config = deep_merge(config, layer)
            layers.append((path, layer))
    validate_schema(config, schema)
    branch_pattern(config["branch"]["pattern"])
    return config, layers


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false", "--no-pager", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FlowkitError(f"Git could not run: {exc}") from exc
    if check and result.returncode:
        raise FlowkitError(f"git {args[0]} failed; verify the repository and ref (exit {result.returncode})")
    return result


def repository(path: Path) -> Path:
    return Path(git(path, "rev-parse", "--show-toplevel").stdout.strip()).resolve()


def native_templates(root: Path, kind: str) -> list[Path]:
    if kind == "pr":
        defaults, named = [], []
        for parent in (root, root / ".github", root / "docs"):
            if not parent.is_dir() or not parent.resolve().is_relative_to(root.resolve()):
                continue
            for entry in parent.iterdir():
                name = entry.name.lower()
                if name in ("pull_request_template.md", "pull_request_template.txt"):
                    defaults.append(entry)
                elif name == "pull_request_template" and entry.is_dir():
                    folder = safe_path(root, entry.relative_to(root).as_posix())
                    named.extend(path for path in folder.iterdir() if path.suffix.lower() in (".md", ".txt"))
        paths = sorted(defaults, key=lambda p: (p.name != p.name.lower(), p.name)) + sorted(named)
        paths.extend(sorted((root / ".gitlab/merge_request_templates").glob("*.md")))
        # macOS/Windows may resolve differently-cased candidates to the same file.
        # Keep one path per filesystem identity, preferring a lowercase default.
        unique: list[Path] = []
        for candidate in paths:
            if candidate.is_file() and not any(candidate.samefile(existing) for existing in unique):
                unique.append(candidate)
        return sorted(unique)
    if kind == "commit":
        result = git(root, "config", "--get", "commit.template", check=False)
        if result.returncode == 0 and result.stdout.strip():
            path = Path(result.stdout.strip()).expanduser()
            path = path if path.is_absolute() else root / path
            if not path.resolve().is_relative_to(root.resolve()):
                raise FlowkitError("Native commit.template is outside the repository; review it manually or set a local template")
            return [path]
    return []


def template_path(root: Path, kind: str, layers: list[tuple[Path, dict[str, Any]]], explicit: str | None = None) -> Path:
    if kind not in KINDS:
        raise FlowkitError(f"Unknown template kind: {kind}")
    if explicit:
        return safe_path(root, explicit)
    local = next(((p, c) for p, c in reversed(layers) if p == root / CONFIG_NAME), None)
    if local and kind in local[1].get("templates", {}):
        return safe_path(root, local[1]["templates"][kind])
    native = native_templates(root, kind)
    if len(native) > 1:
        raise FlowkitError("Multiple native templates; select one with --template or local templates config")
    if native:
        return safe_path(root, native[0].relative_to(root).as_posix())
    for path, config in reversed(layers):
        if kind in config.get("templates", {}):
            return safe_path(path.parent, config["templates"][kind])
    return ASSETS / "templates" / f"{kind}.md"


def render(text: str, values: dict[str, str]) -> str:
    if not isinstance(values, dict) or any(not isinstance(v, str) for v in values.values()):
        raise FlowkitError("Template data must be a JSON object of strings")
    token = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
    missing = set(token.findall(text)) - values.keys()
    if missing:
        raise FlowkitError("Missing template values: " + ", ".join(sorted(missing)))
    # One pass: inserted values cannot introduce executable or recursively expanded tokens.
    return token.sub(lambda match: values[match[1]], text)


def branch_pattern(pattern: str) -> list[tuple[str, str | None, str | None, str | None]]:
    try:
        parts = list(string.Formatter().parse(pattern))
    except ValueError as exc:
        raise FlowkitError("Invalid branch pattern") from exc
    fields = []
    for _, field, spec, conversion in parts:
        if field is not None:
            if field not in ("type", "ticket", "slug") or spec or conversion:
                raise FlowkitError("Branch pattern allows only {type}, {ticket}, {slug}; no expressions")
            fields.append(field)
    if fields.count("type") != 1 or fields.count("slug") != 1 or fields.count("ticket") > 1:
        raise FlowkitError("Branch pattern needs exactly one {type} and {slug}, and at most one {ticket}")
    return parts


def check_branch(root: Path, name: str, config: dict[str, Any]) -> None:
    if not name or len(name) > config["branch"]["max_length"]:
        raise FlowkitError("Branch name is empty or too long")
    if name.startswith("-") or git(root, "check-ref-format", "--branch", name, check=False).returncode:
        raise FlowkitError("Invalid Git branch name")
    tokens = {"type": "(?:" + "|".join(map(re.escape, config["branch"]["types"])) + ")",
              "slug": "[a-z0-9]+(?:-[a-z0-9]+)*", "ticket": "(?:[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-)?"}
    regex = "".join(re.escape(lit) + (tokens[field] if field else "")
                    for lit, field, _, _ in branch_pattern(config["branch"]["pattern"]))
    if not re.fullmatch(regex, name, re.ASCII):
        raise FlowkitError("Branch does not match the configured naming pattern")


def make_branch(root: Path, kind: str, description: str, ticket: str, config: dict[str, Any]) -> str:
    ascii_text = unicodedata.normalize("NFKD", description).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        raise FlowkitError("Provide an ASCII branch description; commit and PR text may use any language")
    if ticket and not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", ticket, re.ASCII):
        raise FlowkitError("Ticket may contain only ASCII letters, digits, and single hyphens")
    name = config["branch"]["pattern"].format(type=kind, ticket=ticket + "-" if ticket else "", slug=slug)
    check_branch(root, name, config)
    return name


def detect_engines(root: Path) -> dict[str, list[str]]:
    patterns = {
        "release-please": ["release-please-config.json", ".release-please-manifest.json"],
        "semantic-release": [".releaserc", ".releaserc.*", "release.config.*"],
        "changesets": [".changeset/config.json"],
        "release-plz": ["release-plz.toml", ".release-plz.toml"],
        "goreleaser": [".goreleaser.yml", ".goreleaser.yaml"],
        "jreleaser": ["jreleaser.yml", "jreleaser.yaml", "jreleaser.toml", "jreleaser.json"],
    }
    found: dict[str, list[str]] = {}
    for engine, globs in patterns.items():
        files = sorted({p.relative_to(root).as_posix() for pattern in globs for p in root.glob(pattern) if p.is_file()})
        if files:
            found[engine] = files
    package = root / "package.json"
    if package.is_file():
        data = load_json(safe_path(root, "package.json"))
        if not isinstance(data, dict) or any(not isinstance(data.get(key, {}), dict) for key in ("dependencies", "devDependencies")):
            raise FlowkitError("package.json and dependency fields must be JSON objects")
        if "release" in data or any("semantic-release" in data.get(key, {}) for key in ("dependencies", "devDependencies")):
            found.setdefault("semantic-release", []).append("package.json")
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        import tomllib
        try:
            data = tomllib.loads(read_text(safe_path(root, "pyproject.toml")))
        except tomllib.TOMLDecodeError as exc:
            raise FlowkitError(f"Invalid pyproject.toml: {exc}") from exc
        if "semantic_release" in data.get("tool", {}):
            found["python-semantic-release"] = ["pyproject.toml"]
    return found


def selected_engine(config: dict[str, Any], found: dict[str, list[str]]) -> str:
    requested = config["release"]["engine"]
    if requested != "auto":
        return requested
    if len(found) > 1:
        raise FlowkitError("Multiple release tools detected; explicitly select the version-owning release.engine")
    return next(iter(found), "none")


def scaffold(root: Path, files: dict[str, str], apply: bool = False) -> list[dict[str, str]]:
    """Preview by default. Existing files are never replaced, even when contents differ."""
    plan = []
    for relative, content in files.items():
        path = safe_path(root, relative)
        for ancestor in [path, *path.parents]:
            if ancestor == root.resolve():
                break
            if ancestor.is_symlink():
                raise FlowkitError(f"Refusing to write through symlink: {relative}")
        exists = path.exists()
        plan.append({"path": relative, "action": "preserve" if exists else "create", "content": "" if exists else content})
    if apply:
        for item in plan:
            if item["action"] == "preserve":
                continue
            path = safe_path(root, item["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(item["content"])
                item["action"] = "created"
            except FileExistsError:
                item["action"] = "preserve"
    return plan


def is_workspace(root: Path) -> bool:
    """Conservative signals; package dependency propagation belongs to native engines."""
    if (root / "pnpm-workspace.yaml").exists() or (root / "lerna.json").exists():
        return True
    if (root / "package.json").is_file():
        package = load_json(safe_path(root, "package.json"))
        if isinstance(package, dict) and "workspaces" in package:
            return True
    if (root / "Cargo.toml").is_file():
        import tomllib
        try:
            if "workspace" in tomllib.loads(read_text(safe_path(root, "Cargo.toml"))):
                return True
        except tomllib.TOMLDecodeError as exc:
            raise FlowkitError(f"Invalid Cargo.toml: {exc}") from exc
    if (root / ".release-please-manifest.json").is_file():
        manifest = load_json(safe_path(root, ".release-please-manifest.json"))
        if isinstance(manifest, dict) and (len(manifest) > 1 or set(manifest) != {"."}):
            return True
    return False
