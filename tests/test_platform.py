"""Filesystem-identity regression checks across case-sensitive and insensitive hosts."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/git-flowkit/scripts"))
import flowkit_core as core


class TemplateIdentityCase(unittest.TestCase):
    def test_native_template_aliases_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            native = root / ".github/pull_request_template.md"
            native.parent.mkdir()
            native.write_text("native", encoding="utf-8")
            alias = root / ".github/PULL_REQUEST_TEMPLATE.md"
            if not alias.exists():
                # A hardlink reproduces case-insensitive identity on Linux too.
                try:
                    os.link(native, alias)
                except OSError:
                    self.skipTest("Hardlink creation is unavailable for this runner")
            self.assertEqual(core.native_templates(root, "pr"), [native])
            self.assertEqual(core.template_path(root, "pr", []), native)


if __name__ == "__main__":
    unittest.main()
