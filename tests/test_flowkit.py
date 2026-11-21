"""Behavior and security regression tests. No network, third-party packages, or credentials."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/git-flowkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import flowkit
import flowkit_core as core
import flowkit_release as release


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"GIT_FLOWKIT_NO_GLOBAL": "1", "GIT_CONFIG_NOSYSTEM": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        core.git(self.root, "init", "-b", "main")
        core.git(self.root, "config", "user.name", "FlowKit Test")
        core.git(self.root, "config", "user.email", "test@example.invalid")
        core.git(self.root, "config", "commit.gpgsign", "false")
        core.git(self.root, "config", "core.hooksPath", "")
        core.git(self.root, "commit", "--allow-empty", "-m", "chore: initialize")
        self.config, self.layers = core.load_config(self.root)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "flowkit.py"), "--repo", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_defaults_validate(self):
        core.validate_schema(self.config, core.load_json(core.ASSETS / "config.schema.json"))

    def test_invalid_configuration(self):
        for value in ({"version": 2}, {"version": True}, {"version": 1, "publsih": True},
                      {"version": 1, "commit": {"max_subject_length": "72"}},
                      {"version": 1, "release": {"rules": {"fix": "huge"}}},
                      {"version": 1, "branch": {"types": []}},
                      {"version": 1, "commit": {"require_scope": "false"}}):
            with self.subTest(value=value):
                self.write(core.CONFIG_NAME, json.dumps(value))
                with self.assertRaises(core.FlowkitError):
                    core.load_config(self.root)

    def test_duplicate_keys_and_nan_rejected(self):
        for text in ('{"version":1,"version":2}', '{"version":NaN}'):
            with self.subTest(text=text):
                with self.assertRaises(core.FlowkitError):
                    core.load_json(self.write("bad.json", text))

    def test_global_local_precedence(self):
        global_config = self.write("home/config.json", '{"version":1,"commit":{"max_subject_length":72,"require_scope":true}}')
        self.write(core.CONFIG_NAME, '{"version":1,"commit":{"max_subject_length":90}}')
        with patch.dict(os.environ, {"GIT_FLOWKIT_NO_GLOBAL": "0", "GIT_FLOWKIT_CONFIG": str(global_config)}):
            config, layers = core.load_config(self.root)
        self.assertEqual(config["commit"]["max_subject_length"], 90)
        self.assertTrue(config["commit"]["require_scope"])
        self.assertEqual(len(layers), 2)

    def test_array_override_and_no_mutation(self):
        source = {"a": {"b": [1, 2]}}
        result = core.deep_merge(source, {"a": {"b": [3]}})
        self.assertEqual(result["a"]["b"], [3])
        self.assertEqual(source["a"]["b"], [1, 2])

    def test_branch_generation(self):
        name = core.make_branch(self.root, "feat", "Add Café Templates!", "DEV-42", self.config)
        self.assertEqual(name, "feat/DEV-42-add-cafe-templates")

    def test_custom_branch_pattern(self):
        self.config["branch"]["pattern"] = "{ticket}{type}/{slug}"
        self.assertEqual(core.make_branch(self.root, "fix", "Bug", "X-2", self.config), "X-2-fix/bug")

    def test_branch_injection_and_invalid_names(self):
        for name in ("--help", "feat/../secret", "feat/has spaces", "feat/a..b", "evil/action", "feat/"):
            with self.subTest(name=name), self.assertRaises(core.FlowkitError):
                core.check_branch(self.root, name, self.config)
        for pattern in ("{type.__class__}/{slug}", "{type}/{slug!r}", "{type}/{type}/{slug}", "{unknown}/{slug}"):
            with self.subTest(pattern=pattern), self.assertRaises(core.FlowkitError):
                core.branch_pattern(pattern)

    def test_non_ascii_slug_needs_explicit_translation(self):
        with self.assertRaises(core.FlowkitError):
            core.make_branch(self.root, "feat", "ภาษาไทย", "", self.config)

    def test_commit_forms(self):
        for message, breaking in (("feat(api): add route", False), ("fix: แก้ไขข้อมูล", False),
                                  ("feat!: change API", True), ("chore(api)!: change defaults", True),
                                  ("fix: change parser\n\nBREAKING CHANGE: old syntax removed", True),
                                  ("fix: change parser\n\nBREAKING-CHANGE: old syntax removed", True)):
            with self.subTest(message=message):
                self.assertEqual(release.parse_commit(message, self.config)["breaking"], breaking)

    def test_invalid_commits(self):
        for message in ("", "Update stuff", "feat:add thing", "feat: ", "feat: a\nbody", "fix: a\n\nBREAKING CHANGE:", "weird: a"):
            with self.subTest(message=message), self.assertRaises(core.FlowkitError):
                release.parse_commit(message, self.config)

    def test_multiline_breaking_notes_in_commit_file_and_git_history(self):
        migration = "Replace --out with --output.\n\n  Set the path explicitly.\n  Keep existing files."
        message = ("fix(cli): change the report option\n\n"
                   f"BREAKING CHANGE: {migration}\n \nRefs #42\nDo not include this reference detail.\n"
                   "BREAKING-CHANGE: Change the config key.\nRename it before upgrading.\n"
                   "Reviewed-by: Example\n")
        notes = [migration, "Change the config key.\nRename it before upgrading."]
        path = self.root / "message.txt"
        path.write_bytes(message.replace("\n", "\r\n").encode("utf-8"))
        checked = self.cli("check-commit", "--file", str(path))
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["breaking_notes"], notes)
        core.git(self.root, "-c", "core.hooksPath=", "commit", "--allow-empty", "-F", str(path))
        preview = self.cli("release-preview", "--current", "1.2.3", "--since", "HEAD~1")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        plan = json.loads(preview.stdout)
        self.assertEqual(plan["next"], "2.0.0")
        self.assertEqual(plan["commits"][0]["breaking_notes"], notes)

    def test_breaking_note_keeps_colons_without_a_footer_separator(self):
        note = "Use the new endpoint.\nhttps://example.invalid/v2\n  Example: keep this indentation."
        message = f"fix: change endpoint\n\nBREAKING CHANGE: {note}\nSigned-off-by: Example"
        self.assertEqual(release.parse_commit(message, self.config)["breaking_notes"], [note])

    def test_commit_scope_and_subject_policy(self):
        self.config["commit"]["require_scope"] = True
        with self.assertRaises(core.FlowkitError):
            release.parse_commit("fix: bug", self.config)
        with self.assertRaises(core.FlowkitError):
            release.parse_commit("fix(core): " + "a" * 200, self.config)

    def test_templates_are_inert_and_unicode_safe(self):
        self.assertEqual(core.render("${summary}: $5", {"summary": "ภาษาไทย ${secret} $(whoami)"}), "ภาษาไทย ${secret} $(whoami): $5")
        for data in ({}, {"summary": {"call": "eval"}}):
            with self.assertRaises(core.FlowkitError):
                core.render("${summary}", data)

    def test_render_crlf_template_preserves_paragraph_spacing(self):
        (self.root / "custom.md").write_bytes(b"${summary}\r\n\r\n${validation}\r\n")
        data = self.write("data.json", '{"summary":"Change","validation":"Not run"}')
        result = self.cli("render", "pr", "--data", str(data), "--template", "custom.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Change\n\nNot run\n")

    def test_template_precedence(self):
        native = self.write(".github/pull_request_template.md", "native")
        global_file = self.write("home/config.json", '{"version":1,"templates":{"pr":"global.md"}}')
        self.write("home/global.md", "global")
        with patch.dict(os.environ, {"GIT_FLOWKIT_NO_GLOBAL": "0", "GIT_FLOWKIT_CONFIG": str(global_file)}):
            _, layers = core.load_config(self.root)
            self.assertEqual(core.template_path(self.root, "pr", layers), native)
            custom = self.write("custom.md", "local")
            self.write(core.CONFIG_NAME, '{"version":1,"templates":{"pr":"custom.md"}}')
            _, layers = core.load_config(self.root)
            self.assertEqual(core.template_path(self.root, "pr", layers), custom)
            self.assertEqual(core.template_path(self.root, "pr", layers, ".github/pull_request_template.md"), native)

    def test_ambiguous_native_template_fails(self):
        self.write(".github/PULL_REQUEST_TEMPLATE/a.md", "a")
        self.write(".github/PULL_REQUEST_TEMPLATE/b.md", "b")
        with self.assertRaises(core.FlowkitError):
            core.template_path(self.root, "pr", [])

    def test_github_templates_in_each_location_reach_doctor_and_render(self):
        data = self.write("data.json", "{}")
        content = "## Summary\n\n## Validation\n"
        self.write("examples/PULL_REQUEST_TEMPLATE/example.md", "outside the supported locations")
        self.write("docs/PULL_REQUEST_TEMPLATE/notes.json", "{}")
        self.write("docs/PULL_REQUEST_TEMPLATE/nested/deeper.md", "nested example")
        for location in ("PULL_REQUEST_TEMPLATE/change.md", "docs/PULL_REQUEST_TEMPLATE/change.txt",
                         ".github/Pull_Request_Template.TxT", "Pull_Request_Template.Md",
                         ".github/Pull_Request_Template/Change.MD"):
            with self.subTest(location=location):
                template = self.write(location, content)
                try:
                    diagnosis = self.cli("doctor")
                    self.assertEqual(diagnosis.returncode, 0, diagnosis.stderr)
                    self.assertEqual(Path(json.loads(diagnosis.stdout)["templates"]["pr"]), template)
                    rendered = self.cli("render", "pr", "--data", str(data))
                    self.assertEqual(rendered.returncode, 0, rendered.stderr)
                    self.assertEqual(rendered.stdout, content)
                finally:
                    template.unlink()

    def test_templates_across_locations_require_a_choice(self):
        self.write(".github/pull_request_template.md", "default\n")
        selected = self.write("docs/PULL_REQUEST_TEMPLATE/feature.txt", "feature\n")
        data = self.write("data.json", "{}")
        ambiguous = self.cli("render", "pr", "--data", str(data))
        self.assertEqual(ambiguous.returncode, 2)
        self.assertIn("Multiple native templates", ambiguous.stderr)
        explicit = self.cli("render", "pr", "--data", str(data), "--template", selected.relative_to(self.root).as_posix())
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(explicit.stdout, "feature\n")

    def test_paths_cannot_escape(self):
        for value in ("../secret", ".git/config", "a/../../secret", "a\\secret", str(self.root / "absolute")):
            with self.subTest(value=value), self.assertRaises(core.FlowkitError):
                core.safe_path(self.root, value)

    def test_symlink_escape_rejected(self):
        outside = self.root.parent
        try:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable for this runner")
        with self.assertRaises(core.FlowkitError):
            core.safe_path(self.root, "escape/data")
        with self.assertRaises(core.FlowkitError):
            core.scaffold(self.root, {"escape/test": "not written"}, True)

    def test_dry_run_and_idempotence(self):
        files = {"a/file.md": "new", "existing.md": "do not replace"}
        self.write("existing.md", "original")
        core.scaffold(self.root, files)
        self.assertFalse((self.root / "a/file.md").exists())
        first = core.scaffold(self.root, files, True)
        second = core.scaffold(self.root, files, True)
        self.assertEqual(first[0]["action"], "created")
        self.assertTrue(all(x["action"] == "preserve" for x in second))
        self.assertEqual(core.read_text(self.root / "existing.md"), "original")

    def test_semver_bumps_and_no_release(self):
        cases = [("fix: a", "1.4.3"), ("feat: a", "1.5.0"), ("feat!: a", "2.0.0"),
                 ("perf: a", "1.4.3"), ("docs: a", None), ("chore: a", None)]
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(release.release_plan("1.4.2", [message], self.config)["next"], expected)

    def test_highest_bump_wins(self):
        plan = release.release_plan("1.4.2", ["fix: a"] * 5 + ["feat: b", "docs!: remove contract"], self.config)
        self.assertEqual(plan["next"], "2.0.0")

    def test_pre1_policy(self):
        self.assertEqual(release.release_plan("0.4.2", ["fix!: a"], self.config)["next"], "1.0.0")
        self.config["release"]["pre1_breaking"] = "minor"
        self.config["release"]["pre1_features"] = "patch"
        self.assertEqual(release.release_plan("0.4.2", ["fix!: a"], self.config)["next"], "0.5.0")
        self.assertEqual(release.release_plan("0.4.2", ["feat: a"], self.config)["next"], "0.4.3")

    def test_custom_release_rules(self):
        self.config["release"]["rules"]["docs"] = "patch"
        self.assertEqual(release.release_plan("1.0.0", ["docs: update contract"], self.config)["next"], "1.0.1")

    def test_valid_semver_and_build_metadata(self):
        for version in ("0.0.0", "1.2.3", "1.2.3-rc.1", "1.2.3+build.001", "1.2.3-alpha.0+abc"):
            with self.subTest(version=version):
                release.parse_version(version)
        self.assertEqual(release.release_plan("1.2.3+abc", ["fix: a"], self.config)["next"], "1.2.4")

    def test_invalid_semver(self):
        for version in ("v1.2.3", "01.2.3", "1.2", "1.2.3-01", "1.2.3-alpha.01", "1.2.3-", "1.2.3+", "１.2.3"):
            with self.subTest(version=version), self.assertRaises(core.FlowkitError):
                release.parse_version(version)

    def test_prerelease_creation_and_unsafe_promotion(self):
        self.assertEqual(release.release_plan("1.2.3", ["feat: a"], self.config, "rc")["next"], "1.3.0-rc.1")
        with self.assertRaises(core.FlowkitError):
            release.release_plan("1.3.0-rc.1", ["fix: a"], self.config)

    def test_revert_and_invalid_messages_fail_closed(self):
        for messages in (["revert: revert a feature"], ["Update stuff"], {"message": "fix: a"}, [42]):
            with self.subTest(messages=messages), self.assertRaises(core.FlowkitError):
                release.release_plan("1.0.0", messages, self.config)

    def test_git_history_and_tag_collision(self):
        base = core.git(self.root, "rev-parse", "HEAD").stdout.strip()
        core.git(self.root, "commit", "--allow-empty", "-m", "feat: actual history")
        messages = release.history(self.root, base)
        self.assertEqual(len(messages), 1)
        plan = release.release_plan("1.0.0", messages, self.config)
        release.check_tag(self.root, plan)
        core.git(self.root, "tag", "v1.1.0")
        with self.assertRaises(core.FlowkitError):
            release.check_tag(self.root, plan)

    def test_shallow_and_invalid_history(self):
        with patch.object(release, "git", return_value=subprocess.CompletedProcess([], 0, "true\n", "")):
            with self.assertRaises(core.FlowkitError):
                release.history(self.root, "HEAD")
        with self.assertRaises(core.FlowkitError):
            release.history(self.root, "--all")

    def test_engine_detection_and_conflict(self):
        self.write(".changeset/config.json", "{}")
        self.write(".releaserc.json", "{}")
        found = core.detect_engines(self.root)
        self.assertEqual(set(found), {"changesets", "semantic-release"})
        with self.assertRaises(core.FlowkitError):
            core.selected_engine(self.config, found)
        self.config["release"]["engine"] = "changesets"
        self.assertEqual(core.selected_engine(self.config, found), "changesets")

    def test_native_python_engine_and_workspaces(self):
        self.write("pyproject.toml", "[tool.semantic_release]\nversion_source = 'tag'\n")
        self.assertIn("python-semantic-release", core.detect_engines(self.root))
        self.write("package.json", '{"workspaces":["packages/*"]}')
        self.assertTrue(core.is_workspace(self.root))

    def test_release_setup_preview_apply_and_existing_engine(self):
        result = self.cli("release-setup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "release-please-config.json").exists())
        result = self.cli("release-setup", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "release-please-config.json").exists())
        result = self.cli("release-setup", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Existing release tooling", result.stderr)

    def test_release_setup_refuses_version_conflict(self):
        self.write("version.txt", "1.2.3\n")
        result = self.cli("release-setup")
        self.assertEqual(result.returncode, 2)
        self.assertIn("disagrees", result.stderr)

    def test_release_setup_uses_named_branch_from_feature_checkout(self):
        core.git(self.root, "branch", "release/stable")
        base = core.git(self.root, "rev-parse", "release/stable").stdout.strip()
        core.git(self.root, "switch", "-c", "chore/bootstrap")
        core.git(self.root, "commit", "--allow-empty", "-m", "fix: local preparation")
        result = self.cli("release-setup", "--branch", "release/stable", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(core.load_json(self.root / "release-please-config.json")["bootstrap-sha"], base)
        workflow = core.read_text(self.root / ".github/workflows/git-flowkit-release.yml")
        self.assertIn('branches: ["release/stable"]', workflow)
        self.assertIn("github.ref == 'refs/heads/release/stable'", workflow)
        self.assertIn('target-branch: "release/stable"', workflow)

    def test_release_setup_can_use_origin_tracking_branch(self):
        core.git(self.root, "update-ref", "refs/remotes/origin/release/stable", "HEAD")
        base = core.git(self.root, "rev-parse", "HEAD").stdout.strip()
        core.git(self.root, "commit", "--allow-empty", "-m", "fix: local preparation")
        result = self.cli("release-setup", "--branch", "release/stable", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(core.load_json(self.root / "release-please-config.json")["bootstrap-sha"], base)

    def test_release_setup_refuses_unknown_target_without_writing(self):
        # A similarly named remote-tracking branch must not satisfy the target lookup.
        core.git(self.root, "update-ref", "refs/remotes/origin/stable/older", "HEAD")
        result = self.cli("release-setup", "--branch", "stable", "--apply")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("stable", result.stderr)
        self.assertEqual(core.git(self.root, "status", "--porcelain").stdout, "")

    def test_release_setup_refuses_shallow_clone_with_hidden_tag(self):
        core.git(self.root, "tag", "v1.0.0")
        core.git(self.root, "commit", "--allow-empty", "-m", "docs: update guide")
        with tempfile.TemporaryDirectory() as clone:
            core.git(Path(clone), "clone", "--depth=1", self.root.as_uri(), ".")
            self.assertEqual(core.git(Path(clone), "tag", "--list").stdout, "")
            result = subprocess.run([sys.executable, str(SCRIPTS / "flowkit.py"), "--repo", clone,
                                     "release-setup", "--apply"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Shallow", result.stderr)
            self.assertEqual(core.git(Path(clone), "status", "--porcelain").stdout, "")

    def test_release_setup_refuses_conflicting_release_tips(self):
        core.git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        core.git(self.root, "commit", "--allow-empty", "-m", "fix: unpublished work")
        result = self.cli("release-setup", "--apply")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("origin/main differ", result.stderr)
        self.assertEqual(core.git(self.root, "status", "--porcelain").stdout, "")

    def test_release_setup_seed_is_a_stable_manifest_baseline(self):
        result = self.cli("release-setup", "--initial-version", "1.4.2-rc.1", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("stable version", result.stderr)
        self.assertFalse((self.root / ".release-please-manifest.json").exists())
        result = self.cli("release-setup", "--initial-version", "1.4.2", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(core.load_json(self.root / ".release-please-manifest.json"), {".": "1.4.2"})
        self.assertEqual(core.read_text(self.root / "version.txt").strip(), "1.4.2")

    def test_release_setup_refuses_existing_tags(self):
        core.git(self.root, "tag", "v1.0.0")
        self.assertEqual(self.cli("release-setup").returncode, 2)

    def test_release_setup_and_preview_refuse_monorepo(self):
        self.write("pnpm-workspace.yaml", "packages: ['packages/*']\n")
        self.write("commits.json", '["fix: a"]')
        self.assertEqual(self.cli("release-setup").returncode, 2)
        self.assertEqual(self.cli("release-preview", "--current", "1.0.0", "--commits", str(self.root / "commits.json")).returncode, 2)

    def test_cli_smoke(self):
        for args in (("doctor",), ("validate",), ("config",), ("check-commit", "--message", "fix: แก้ไข"), ("branch", "feat", "Add templates")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("check-commit", "--message", "bad").returncode, 2)

    def test_init_default_dry_run_and_no_overwrite(self):
        self.assertEqual(self.cli("init").returncode, 0)
        self.assertFalse((self.root / core.CONFIG_NAME).exists())
        self.assertEqual(self.cli("init", "--apply").returncode, 0)
        self.write(core.CONFIG_NAME, '{"version":1,"commit":{"require_scope":true}}')
        self.assertEqual(self.cli("init", "--apply").returncode, 0)
        self.assertTrue(core.load_config(self.root)[0]["commit"]["require_scope"])


class MergeEvidenceCase(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        sha = "a" * 40
        self.data = {"head_sha": sha, "expected_head_sha": sha, "fetched_at": self.now.isoformat(),
                     "draft": False, "mergeable": True, "up_to_date": True, "protection_verified": True,
                     "unresolved_threads": 0, "approvals": 1, "reviews_head_sha": sha,
                     "required_checks": ["CI"], "checks": [{"name": "CI", "head_sha": sha, "status": "completed", "conclusion": "success"}]}

    def test_ready(self):
        self.assertTrue(release.merge_readiness(self.data, 1, self.now)["ready"])

    def test_fail_closed_on_unknown_state(self):
        for key in self.data:
            with self.subTest(key=key):
                data = dict(self.data)
                data.pop(key)
                self.assertFalse(release.merge_readiness(data, 1, self.now)["ready"])

    def test_stale_future_and_naive_timestamps(self):
        for time in ((self.now - timedelta(minutes=6)).isoformat(), (self.now + timedelta(seconds=1)).isoformat(), "2026-11-20T00:00:00"):
            with self.subTest(time=time):
                data = dict(self.data, fetched_at=time)
                self.assertFalse(release.merge_readiness(data, 1, self.now)["ready"])

    def test_wrong_head_failed_checks_and_boolean_approvals(self):
        for change in ({"expected_head_sha": "b" * 40}, {"approvals": True}, {"draft": True}, {"unresolved_threads": 1}):
            with self.subTest(change=change):
                self.assertFalse(release.merge_readiness(dict(self.data, **change), 1, self.now)["ready"])
        for conclusion in ("failure", "neutral", "skipped", "cancelled", None):
            with self.subTest(conclusion=conclusion):
                data = copy.deepcopy(self.data)
                data["checks"][0]["conclusion"] = conclusion
                self.assertFalse(release.merge_readiness(data, 1, self.now)["ready"])

    def test_duplicate_check_names_block(self):
        self.data["checks"] *= 2
        self.assertFalse(release.merge_readiness(self.data, 1, self.now)["ready"])


if __name__ == "__main__":
    unittest.main()
