#!/usr/bin/env python3
"""Portable, offline Git workflow CLI. No commit, push, merge, tag, or publish commands."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from flowkit_core import (ASSETS, CONFIG_NAME, KINDS, FlowkitError, check_branch, detect_engines,
                          git, global_path, is_workspace, json_text, load_config, load_json, make_branch,
                          native_templates, read_text, render, repository, scaffold,
                          selected_engine, template_path)
from flowkit_release import (bootstrap_sha, check_tag, history, merge_readiness, parse_commit, parse_version, release_plan)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path.cwd(), help="Target Git working tree (before the command)")
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("doctor", "config", "validate"):
        commands.add_parser(name)
    init = commands.add_parser("init", help="Preview missing config and editable templates")
    init.add_argument("--apply", action="store_true")
    init.add_argument("--global", dest="global_config", action="store_true")
    branch = commands.add_parser("branch", help="Generate a name without creating a branch")
    branch.add_argument("type")
    branch.add_argument("description")
    branch.add_argument("--ticket", default="")
    commands.add_parser("check-branch").add_argument("name")
    commit = commands.add_parser("check-commit")
    source = commit.add_mutually_exclusive_group(required=True)
    source.add_argument("--message")
    source.add_argument("--file", type=Path)
    template = commands.add_parser("render", help="Render inert ${field} placeholders to stdout")
    template.add_argument("kind", choices=KINDS)
    template.add_argument("--data", type=Path, required=True)
    template.add_argument("--template", help="Repository-relative explicit template")
    preview = commands.add_parser("release-preview", help="Advisory, read-only SemVer calculation")
    preview.add_argument("--current", required=True)
    source = preview.add_mutually_exclusive_group(required=True)
    source.add_argument("--since", help="Explicit last-release ref or initial commit SHA")
    source.add_argument("--commits", type=Path, help="JSON array of commit messages")
    preview.add_argument("--prerelease", choices=("alpha", "beta", "rc"))
    setup = commands.add_parser("release-setup", help="Scaffold opt-in Release Please; never overwrite native engines")
    setup.add_argument("--apply", action="store_true")
    setup.add_argument("--branch", default="main", help="Release branch used for the bootstrap boundary and workflow trigger")
    setup.add_argument("--initial-version", default="0.0.0",
                       help="Manifest and version.txt baseline (default: 0.0.0). To choose the first release "
                            "from zero, set initial-version in the generated Release Please package config.")
    commands.add_parser("merge-check").add_argument("--evidence", type=Path, required=True)
    return p


def init_files(root: Path, global_mode: bool) -> dict[str, str]:
    prefix = "templates/" if global_mode else ".git-flowkit/templates/"
    # Do not install local pointers: native repository templates must keep priority over defaults.
    config = {"version": 1, "templates": {kind: prefix + kind + ".md" for kind in KINDS}} if global_mode else {"version": 1}
    name = global_path().name if global_mode else CONFIG_NAME
    files = {name: json_text(config)}
    for kind in KINDS:
        files[prefix + kind + ".md"] = read_text(ASSETS / "templates" / f"{kind}.md")
    return files


def setup_release(root: Path, args: argparse.Namespace, config: dict) -> list[dict[str, str]]:
    engines = detect_engines(root)
    if engines:
        raise FlowkitError("Existing release tooling detected; adopt it instead of installing a second owner: " + ", ".join(engines))
    if config["release"]["engine"] not in ("auto", "none", "release-please"):
        raise FlowkitError("release-setup scaffolds only Release Please; retain the configured native engine")
    if parse_version(args.initial_version)[3]:
        raise FlowkitError("Bootstrap a stable version; configure prereleases in the native engine")
    if is_workspace(root):
        raise FlowkitError("Monorepo release setup requires a reviewed native-engine manifest")
    if (root / "version.txt").exists() and read_text(root / "version.txt").strip() != args.initial_version:
        raise FlowkitError("Existing version.txt disagrees with --initial-version; reconcile before setup")
    if not all(c.isalnum() or c in "/_-" for c in args.branch) or git(root, "check-ref-format", "--branch", args.branch, check=False).returncode:
        raise FlowkitError("Use a valid plain branch name without workflow glob characters")
    base = bootstrap_sha(root, args.branch)
    # This adapter owns standard v-prefixed tags and these default release rules only.
    expected = {"feat": "minor", "fix": "patch", "perf": "patch"}
    if config["release"]["tag_prefix"] != "v" or config["release"]["rules"] != expected:
        raise FlowkitError("Custom release rules/tag prefixes need a reviewed native-engine configuration")
    native = {"$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
              "bootstrap-sha": base,
              "packages": {".": {"release-type": "simple", "include-component-in-tag": False,
                                    "bump-minor-pre-major": config["release"]["pre1_breaking"] == "minor",
                                    "bump-patch-for-minor-pre-major": config["release"]["pre1_features"] == "patch"}}}
    workflow = read_text(ASSETS / "release-please" / "workflow.yml").replace("__DEFAULT_BRANCH__", args.branch)
    return scaffold(root, {"release-please-config.json": json_text(native),
                           ".release-please-manifest.json": json_text({".": args.initial_version}),
                           "version.txt": args.initial_version + "\n",
                           "CHANGELOG.md": "# Changelog\n\nChanges are maintained by Release Please.\n",
                           ".github/workflows/git-flowkit-release.yml": workflow}, args.apply)


def run(args: argparse.Namespace) -> int:
    if args.command == "init" and args.global_config:
        root = global_path().parent.resolve()
        print(json_text({"applied": args.apply, "files": scaffold(root, init_files(root, True), args.apply)}), end="")
        return 0
    root = repository(args.repo)
    config, layers = load_config(root)
    command = args.command
    result = None
    if command == "init":
        result = {"applied": args.apply, "files": scaffold(root, init_files(root, False), args.apply),
                  "next": "Edit .git-flowkit.json to point templates.<kind> at an editable template; native templates stay authoritative until selected."}
    elif command == "config":
        result = {"config": config, "layers": [str(path) for path, _ in layers],
                  "template_precedence": "explicit > repository config > native > global config > bundled"}
    elif command in ("doctor", "validate"):
        found = detect_engines(root)
        engine = selected_engine(config, found)
        templates = {kind: str(template_path(root, kind, layers)) for kind in KINDS}
        for path in templates.values():
            read_text(Path(path))
        result = {"valid": True, "root": str(root), "branch": git(root, "branch", "--show-current").stdout.strip(),
                  "dirty": bool(git(root, "status", "--porcelain").stdout), "release_engine": engine,
                  "engine_signals": found, "templates": templates,
                  "unverified": ["Provider branch protections and required checks", "Native engine runtime behavior"]}
    elif command == "branch":
        print(make_branch(root, args.type, args.description, args.ticket, config))
        return 0
    elif command == "check-branch":
        check_branch(root, args.name, config)
        result = {"valid": True, "branch": args.name}
    elif command == "check-commit":
        result = dict(parse_commit(read_text(args.file) if args.file else args.message, config), valid=True)
    elif command == "render":
        text = render(read_text(template_path(root, args.kind, layers, args.template)), load_json(args.data))
        if args.kind in ("commit", "merge"):
            parse_commit(text, config)
        print(text, end="" if text.endswith("\n") else "\n")
        return 0
    elif command == "release-preview":
        if is_workspace(root):
            raise FlowkitError("Monorepo previews require the native engine and its dependency graph")
        engine = selected_engine(config, detect_engines(root))
        messages = load_json(args.commits) if args.commits else history(root, args.since)
        result = release_plan(args.current, messages, config, args.prerelease)
        result["engine"] = engine
        check_tag(root, result)
    elif command == "release-setup":
        result = {"applied": args.apply, "files": setup_release(root, args, config),
                  "next": "Review the files and required CI checks; explicitly enable FLOWKIT_RELEASE_ENABLED only after merging the setup."}
    elif command == "merge-check":
        result = merge_readiness(load_json(args.evidence), config["merge"]["required_approvals"])
        print(json_text(result), end="")
        return 0 if result["ready"] else 1
    print(json_text(result), end="")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        return run(parser().parse_args())
    except (FlowkitError, OSError) as exc:
        print(json_text({"error": str(exc)}), file=sys.stderr, end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
