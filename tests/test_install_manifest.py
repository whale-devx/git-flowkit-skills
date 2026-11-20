import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.install_smoke import check_installed_paths, smoke


class InstalledManifestTests(unittest.TestCase):
    def test_install_journeys_start_with_an_isolated_environment(self):
        inherited = {"PATH": "fixture-bin", "FLOWKIT_TEST_MARKER": "parent-only",
                     "NODE_OPTIONS": "parent-option", "npm_config_userconfig": "parent-config"}
        for source in ("main", "candidate"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                with patch.dict(os.environ, inherited, clear=True), patch(
                    "tools.install_smoke.subprocess.run", side_effect=InterruptedError
                ) as child:
                    with self.assertRaises(InterruptedError):
                        smoke(source, root)
                env = {k.upper(): v for k, v in child.call_args.kwargs["env"].items()}
                self.assertNotIn("FLOWKIT_TEST_MARKER", env)
                self.assertNotIn("NODE_OPTIONS", env)
                self.assertEqual(env["PATH"], "fixture-bin")
                self.assertEqual(env["NPM_CONFIG_IGNORE_SCRIPTS"], "true")
                for key in ("HOME", "TMPDIR", "NPM_CONFIG_CACHE", "NPM_CONFIG_USERCONFIG",
                            "NPM_CONFIG_GLOBALCONFIG"):
                    self.assertTrue(Path(env[key]).is_relative_to(root), key)

    def test_exact_tree_including_unexpected_nested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory)
            (skill / "SKILL.md").write_text("example", encoding="utf-8")
            expected = {"SKILL.md"}
            check_installed_paths(skill, expected)
            (skill / "scripts").mkdir()
            (skill / "scripts/stale.py").touch()
            with self.assertRaisesRegex(RuntimeError, "stale.py"):
                check_installed_paths(skill, expected)
            with self.assertRaisesRegex(RuntimeError, "missing.md"):
                check_installed_paths(skill, {"missing.md"})
