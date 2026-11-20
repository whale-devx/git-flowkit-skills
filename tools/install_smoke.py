"""Network integration test. Run from a checkout with Python, Git and Node installed."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "skills@1.9.0"
REMOTE = "whale-devx/git-flowkit-skills"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_installed_paths(skill, expected):
    actual = set()
    for path in skill.rglob("*"):
        relative = path.relative_to(skill).as_posix()
        require(not path.is_symlink() and path.resolve().is_relative_to(skill.resolve()),
                f"Expected a copied package entry: {relative}")
        if path.is_file():
            actual.add(relative)
    require(actual == expected, f"Installed file set differs: {sorted(actual ^ expected)}")


def smoke(source, temp):
    install = temp / "installation"
    target = temp / "example ทดสอบ"
    home = temp / "home"
    scratch = temp / "tmp"
    for directory in (install, target, home, scratch):
        directory.mkdir()
    # Public-source and local installs only need the system's executable lookup.
    system_keys = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "PATHEXT")
    env = {key: os.environ[key] for key in system_keys if key in os.environ}
    user_config, global_config = home / "user.npmrc", home / "global.npmrc"
    user_config.touch()
    global_config.touch()
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home),
               LOCALAPPDATA=str(home), XDG_CONFIG_HOME=str(home), CODEX_HOME=str(home / "codex"),
               TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
               NPM_CONFIG_USERCONFIG=str(user_config), NPM_CONFIG_GLOBALCONFIG=str(global_config),
               NPM_CONFIG_CACHE=str(temp / "npm"), NPM_CONFIG_IGNORE_SCRIPTS="true",
               DISABLE_TELEMETRY="1", CI="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", GIT_FLOWKIT_NO_GLOBAL="1")

    def run(*args, cwd=target, offline=False):
        child = dict(env, GIT_ALLOW_PROTOCOL="") if offline else env
        return subprocess.run(args, cwd=cwd, env=child, check=True, timeout=120,
                              stdout=subprocess.PIPE, encoding="utf-8").stdout.strip()

    run("git", "init", "-q", cwd=install)
    revision = run("git", "rev-parse", "HEAD", cwd=ROOT)
    if source == "candidate":
        require(not run("git", "status", "--porcelain", "--", "skills/git-flowkit", cwd=ROOT),
                "Commit skill changes before checking candidate provenance")
    else:
        revision = run("git", "ls-remote", "https://github.com/" + REMOTE, "HEAD").split()[0]
    npx = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    require(npx, "Install Node.js and npx before running the integration test")
    print(run(npx, "--yes", PACKAGE, "add", REMOTE if source == "main" else str(ROOT),
              "--skill", "git-flowkit", "--agent", "codex", "--copy", "--yes", cwd=install))
    if source == "main":
        lock = json.loads((install / "skills-lock.json").read_text(encoding="utf-8"))
        require(lock["skills"]["git-flowkit"]["commit"] == revision, "Main changed during install")
    skill_file, = install.rglob("SKILL.md")
    skill = skill_file.parent
    require(skill.resolve().is_relative_to(install), "Expected a project-local install")
    listing = run("git", "ls-tree", "-r", revision, "skills/git-flowkit", cwd=ROOT)
    expected_paths = {item.split("\t", 1)[1].removeprefix("skills/git-flowkit/")
                      for item in listing.splitlines()}
    check_installed_paths(skill, expected_paths)
    for item in listing.splitlines():
        metadata, name = item.split("\t", 1)
        installed = skill / Path(name).relative_to("skills/git-flowkit")
        expected = metadata.split()[-1]
        actual = run("git", "hash-object", "--path", name, str(installed), cwd=ROOT)
        require(actual == expected, f"Installed file differs: {name}")
    print(f"{source} {revision}: verified installed files at {skill}", flush=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-q", "--allow-empty", "-m", "chore: initialize")

    def cli(*args):
        return run(sys.executable, str(skill / "scripts/flowkit.py"), "--repo", str(target),
                   *args, offline=True)

    def snapshot():
        return {p.relative_to(target): p.read_bytes() for p in target.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(target).parts}

    initial = snapshot()
    refs = run("git", "show-ref")
    cli("doctor")
    cli("config")
    cli("init")
    require(snapshot() == initial, "Preview wrote to target")
    cli("init", "--apply")
    config = target / ".git-flowkit.json"
    data = temp / "data.json"
    data.write_text("{}", encoding="utf-8")
    global_config = home / "config.json"
    global_config.write_text(json.dumps({"version": 1, "templates": {"pr": "global.md"}}), encoding="utf-8")
    (home / "global.md").write_text("Global instructions", encoding="utf-8")
    env.update(GIT_FLOWKIT_CONFIG=str(global_config), GIT_FLOWKIT_NO_GLOBAL="0")
    require(cli("render", "pr", "--data", str(data)) == "Global instructions", "Global template ignored")
    native = target / ".github/pull_request_template.md"
    native.parent.mkdir(exist_ok=True)
    native.write_text("## Review checklist", encoding="utf-8")
    require(cli("render", "pr", "--data", str(data)) == "## Review checklist", "Native Markdown changed")
    config.write_text(json.dumps({"version": 1, "templates": {"pr": "custom.md"}}), encoding="utf-8")
    (target / "custom.md").write_text("${summary}\n${validation}", encoding="utf-8")
    before = snapshot()
    cli("init", "--apply")
    require(snapshot() == before, "Repeated apply changed existing files")
    branch = cli("branch", "feat", "add café", "--ticket", "DEV-42")
    require(branch == "feat/DEV-42-add-cafe", "Unexpected branch")
    cli("check-branch", branch)
    cli("check-commit", "--message", "fix: แก้ไข")
    footer = "BREAKING CHANGE: migrate old settings"
    values = dict(summary="ทดสอบ", validation="Branch check passed. UI tests not run.",
                  title="feat!: change settings", breaking_changes=footer, references="")
    data.write_text(json.dumps(values), encoding="utf-8")
    require(cli("render", "pr", "--data", str(data)) == values["summary"] + "\n" + values["validation"],
            "Custom PR text or validation evidence changed")
    require(cli("render", "pr", "--data", str(data), "--template", ".github/pull_request_template.md")
            == "## Review checklist", "Explicit override ignored")
    merge = cli("render", "merge", "--data", str(data))
    require(footer in merge.splitlines(), "Squash message lost its breaking footer")
    data.write_text(json.dumps([merge]), encoding="utf-8")
    plan = json.loads(cli("release-preview", "--current", "1.0.0", "--commits", str(data)))
    require(plan["next"] == "2.0.0", "Incorrect release preview")
    require(snapshot() == before and refs == run("git", "show-ref") and
            not run("git", "diff", "--cached", "--name-only"), "Workflow changed files or Git state")
    print(f"{source} {revision}: installed helper journey passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=("main", "candidate"))
    with tempfile.TemporaryDirectory() as directory:
        smoke(parser.parse_args().source, Path(directory))
