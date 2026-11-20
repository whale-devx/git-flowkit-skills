import tempfile
import unittest
from pathlib import Path

from tools.install_smoke import check_installed_paths


class InstalledManifestTests(unittest.TestCase):
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
