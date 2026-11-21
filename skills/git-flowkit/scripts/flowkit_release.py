"""Conventional Commit validation and advisory SemVer planning; never publishes."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flowkit_core import FlowkitError, git

HEADER = re.compile(r"([a-z][a-z0-9-]*)(?:\(([A-Za-z0-9_./-]+)\))?(!)?: (\S.*)")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")
LEVELS = {"none": 0, "patch": 1, "minor": 2, "major": 3}


def breaking_notes(lines: list[str]) -> list[str]:
    notes: list[list[str]] = []
    current = None
    for line in lines:
        match = re.fullmatch(r"BREAKING[ -]CHANGE: *(.*)", line)
        if match:
            if not match[1].strip():
                raise FlowkitError("BREAKING CHANGE needs a description on the same line")
            current = [match[1]]
            notes.append(current)
        elif re.match(r"\w[\w-]*(?:: | #)", line):
            current = None
        elif current is not None:
            current.append(line)
    for note in notes:
        while not note[-1].strip():
            note.pop()
    return ["\n".join(note) for note in notes]


def parse_commit(message: str, config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(message, str) or not message or "\x00" in message:
        raise FlowkitError("Commit must be a nonempty string without NUL bytes")
    lines = message.splitlines()
    match = HEADER.fullmatch(lines[0])
    if not match:
        raise FlowkitError("Expected type(scope)!: description; scope and ! are optional")
    kind, scope, bang, description = match.groups()
    if kind not in config["commit"]["types"]:
        raise FlowkitError(f"Commit type {kind!r} is not allowed by repository policy")
    if len(lines[0]) > config["commit"]["max_subject_length"]:
        raise FlowkitError("Commit subject exceeds configured maximum length")
    if config["commit"]["require_scope"] and not scope:
        raise FlowkitError("Repository policy requires a commit scope")
    if len(lines) > 1 and lines[1].strip():
        raise FlowkitError("Separate commit subject and body with a blank line")
    footers = breaking_notes(lines[2:])
    return {"type": kind, "scope": scope, "description": description,
            "subject": lines[0], "breaking": bool(bang or footers), "breaking_notes": footers}


def parse_version(value: str) -> tuple[int, int, int, str | None]:
    match = VERSION.fullmatch(value)
    if not match:
        raise FlowkitError("Version must be SemVer without a v prefix (for example 1.4.2)")
    major, minor, patch, pre, _ = match.groups()
    if pre and any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in pre.split(".")):
        raise FlowkitError("Numeric prerelease identifiers cannot contain leading zeroes")
    return int(major), int(minor), int(patch), pre


def release_plan(current: str, messages: list[Any], config: dict[str, Any], prerelease: str | None = None) -> dict[str, Any]:
    major, minor, patch, pre = parse_version(current)
    if pre:
        raise FlowkitError("Continuation or promotion of prereleases requires the native release engine")
    if prerelease and prerelease not in ("alpha", "beta", "rc"):
        raise FlowkitError("Prerelease channel must be alpha, beta, or rc")
    if not isinstance(messages, list):
        raise FlowkitError("Commits input must be a JSON array of strings or {message, sha} objects")
    entries = []
    bump = "none"
    for value in messages:
        if isinstance(value, str):
            message, sha = value, None
        elif isinstance(value, dict) and isinstance(value.get("message"), str):
            message, sha = value["message"], value.get("sha")
            if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{7,64}", sha)):
                raise FlowkitError("Commit sha must be a hexadecimal object ID")
        else:
            raise FlowkitError("Each commit must contain a message string")
        entry = parse_commit(message, config)
        if entry["type"] == "revert":
            raise FlowkitError("Reverts require native-engine analysis; the preview does not cancel commits")
        impact = "major" if entry["breaking"] else config["release"]["rules"].get(entry["type"], "none")
        if major == 0 and impact == "major" and config["release"]["pre1_breaking"] == "minor":
            impact = "minor"
        elif major == 0 and impact == "minor" and config["release"]["pre1_features"] == "patch":
            impact = "patch"
        entries.append(dict(entry, sha=sha, impact=impact))
        if LEVELS[impact] > LEVELS[bump]:
            bump = impact
    next_version = None
    if bump != "none":
        parts = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0), "patch": (major, minor, patch + 1)}[bump]
        next_version = ".".join(map(str, parts)) + (f"-{prerelease}.1" if prerelease else "")
    return {"advisory": True, "current": current, "bump": bump, "next": next_version,
            "tag": config["release"]["tag_prefix"] + next_version if next_version else None,
            "commits": entries,
            "limitations": ["Native release-engine configuration is authoritative.",
                            "No monorepo dependency propagation, revert cancellation, or prerelease promotion.",
                            "Only local tags are checked; recheck the remote before publishing."]}


def history(root: Path, since: str) -> list[dict[str, str]]:
    if git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        raise FlowkitError("Shallow history cannot be used for release planning; fetch full history explicitly")
    base = git(root, "rev-parse", "--verify", "--end-of-options", since + "^{commit}").stdout.strip()
    head = git(root, "rev-parse", "--verify", "HEAD").stdout.strip()
    if git(root, "merge-base", "--is-ancestor", base, head, check=False).returncode:
        raise FlowkitError("The release base is not an ancestor of HEAD")
    raw = git(root, "log", "--no-merges", "--reverse", "--format=%H%x00%B%x00", f"{base}..{head}").stdout
    parts = raw.split("\x00")
    return [{"sha": parts[i].strip(), "message": parts[i + 1].rstrip()} for i in range(0, len(parts) - 1, 2) if parts[i].strip()]


def check_tag(root: Path, plan: dict[str, Any]) -> None:
    tag = plan["tag"]
    if tag:
        if git(root, "check-ref-format", "refs/tags/" + tag, check=False).returncode:
            raise FlowkitError("Configured tag prefix produces an invalid Git tag")
        result = git(root, "show-ref", "--verify", "--quiet", "refs/tags/" + tag, check=False)
        if result.returncode == 0:
            raise FlowkitError(f"Local tag {tag} already exists; never replace a published version")
        if result.returncode != 1:
            raise FlowkitError("Could not verify local tag availability")


def merge_readiness(data: dict[str, Any], required_approvals: int, now: datetime | None = None) -> dict[str, Any]:
    """Conservative offline check of a provider-normalized evidence snapshot, not authorization."""
    if not isinstance(data, dict):
        raise FlowkitError("Merge evidence must be an object")
    now = now or datetime.now(timezone.utc)
    problems = []
    head = data.get("head_sha")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head) or head != data.get("expected_head_sha"):
        problems.append("Missing, invalid, or changed HEAD SHA")
    try:
        fetched = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
        age = (now - fetched).total_seconds()
        if not 0 <= age <= 300:
            problems.append("Evidence is stale or from the future")
    except (KeyError, TypeError, ValueError, AttributeError):
        problems.append("Missing timezone-aware fetched_at timestamp")
    for field, expected in (("draft", False), ("mergeable", True), ("up_to_date", True), ("protection_verified", True)):
        if data.get(field) is not expected:
            problems.append(f"{field} must be {expected}")
    if type(data.get("unresolved_threads")) is not int or data["unresolved_threads"] != 0:
        problems.append("Unresolved review threads or unknown thread state")
    approvals = data.get("approvals")
    if type(approvals) is not int or approvals < required_approvals:
        problems.append("Insufficient verified approvals for the current HEAD")
    if data.get("reviews_head_sha") != head:
        problems.append("Reviews were not verified for the current HEAD")
    required, checks = data.get("required_checks"), data.get("checks")
    if not isinstance(required, list) or not all(isinstance(name, str) and name for name in required) or not isinstance(checks, list):
        problems.append("Required checks or check results are unknown")
    else:
        for name in required:
            matches = [c for c in checks if isinstance(c, dict) and c.get("name") == name]
            if len(matches) != 1 or matches[0].get("head_sha") != head or matches[0].get("status") != "completed" or matches[0].get("conclusion") != "success":
                problems.append(f"Required check is missing, ambiguous, stale, or unsuccessful: {name}")
    return {"advisory": True, "ready": not problems, "blockers": problems,
            "notice": "Re-fetch live provider policy and HEAD immediately before an explicitly authorized merge."}
