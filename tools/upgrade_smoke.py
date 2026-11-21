"""Rehearse a project-local Skills CLI upgrade and rollback against public Git revisions."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from install_smoke import PACKAGE, REMOTE, ROOT, require

PREVIOUS = "724bb8b0d077142fc22f2274d342656cb50a9bbb"
UPGRADE = "a15e6e024d39c93592f655d5a903c15342d5c45f"
SKILL = Path(".agents/skills/git-flowkit")


def verify_copy(project, revision, env):
    archive = subprocess.run(
        ["git", "-C", str(ROOT), "archive", "--format=zip", revision, "skills/git-flowkit"],
        check=True, capture_output=True, env=env, timeout=30,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        expected = {entry.filename.removeprefix("skills/git-flowkit/"): source.read(entry)
                    for entry in source.infolist() if not entry.is_dir()}
    skill = project / SKILL
    require(skill.resolve() == skill, "Expected a project-local copy")
    installed = {}
    for path in skill.rglob("*"):
        require(not path.is_symlink() and path.resolve().is_relative_to(skill), "Unexpected link in copy")
        if path.is_file():
            installed[path.relative_to(skill).as_posix()] = path.read_bytes()
    require(installed == expected, f"Installed files differ from Git revision {revision}")
    lock = json.loads((project / "skills-lock.json").read_bytes())
    require(lock["skills"]["git-flowkit"]["commit"] == revision, "Installer lock has the wrong commit")
    return len(expected)


def rehearse(temp):
    project, home = temp / "project", temp / "home"
    project.mkdir()
    home.mkdir()
    env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "ComSpec", "PATHEXT", "TEMP", "TMP")
           if k in os.environ}
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home), LOCALAPPDATA=str(home),
               XDG_CONFIG_HOME=str(home), CODEX_HOME=str(home / "codex"), npm_config_cache=str(temp / "npm"),
               DISABLE_TELEMETRY="1", CI="1", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1", GIT_FLOWKIT_NO_GLOBAL="1")
    npx = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    require(npx, "Install Node.js and npx before running this rehearsal")

    def run(*args):
        return subprocess.run(args, cwd=project, env=env, check=True, capture_output=True,
                              encoding="utf-8", timeout=150).stdout.strip()

    run("git", "init", "-q")
    policy = {"version": 1, "branch": {"pattern": "team/{type}/{ticket}{slug}"},
              "templates": {"pr": ".git-flowkit/templates/team.md"}}
    files = {".git-flowkit.json": json.dumps(policy), ".git-flowkit/templates/team.md": "Review ${summary}",
             "pr.json": '{"summary":"migration"}', ".agents/skills/another/SKILL.md": "# Another skill\n"}
    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())
    for phase, revision in (("baseline", PREVIOUS), ("upgrade", UPGRADE), ("rollback", PREVIOUS)):
        if phase == "upgrade":
            (project / SKILL / "local-note.txt").write_bytes(b"Untracked note in the managed copy")
        url = f"https://github.com/{REMOTE}/tree/{revision}"
        run(npx, "--yes", PACKAGE, "add", url, "--skill", "git-flowkit", "--agent", "codex", "--copy", "--yes")
        count = verify_copy(project, revision, env)
        cli = [sys.executable, "-B", str(project / SKILL / "scripts/flowkit.py"), "--repo", str(project)]
        require(run(*cli, "branch", "feat", "upgrade test", "--ticket", "DEV-42") == "team/feat/DEV-42-upgrade-test",
                "Installed helper ignored the project's branch policy")
        require(run(*cli, "render", "pr", "--data", "pr.json") == "Review migration",
                "Installed helper ignored the project's template")
        require(all((project / name).read_bytes() == content.encode() for name, content in files.items()),
                "Project data changed during the install")
        if phase == "baseline":
            run("git", "add", "--all")
            run("git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "Record original project installation")
            head = run("git", "rev-parse", "HEAD")
        else:
            require(run("git", "rev-parse", "HEAD") == head and not run("git", "diff", "--cached", "--name-only"),
                    "Project history or index changed")
        if phase == "rollback":
            require(not run("git", "status", "--porcelain", "--untracked-files=all"),
                    "Restored project differs from its baseline")
        print(f"{phase} {revision}: verified {count} installed files, lock, project policy and template", flush=True)


if __name__ == "__main__":
    try:
        with tempfile.TemporaryDirectory() as directory:
            rehearse(Path(directory).resolve())
    except subprocess.CalledProcessError as error:
        sys.exit(error.stderr or str(error))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
