"""Keep the Ubuntu Bubblewrap profile setup ahead of repository checkout."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ("ci-fast.yml", "ci-full.yml")
SETUP = (
    "sudo apt-get update",
    "sudo apt-get install --yes bubblewrap apparmor-profiles",
    "sudo apparmor_parser -r /usr/share/apparmor/extra-profiles/bwrap-userns-restrict",
)


class UbuntuSandboxSetupTests(unittest.TestCase):
    def test_setup_loads_restrictive_profile_before_checkout(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow):
                source = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
                setup = source.index("      - name: Set up the Ubuntu sandbox")
                checkout = source.index("      - uses: actions/checkout@")
                setup_block = source[setup:checkout]

                self.assertLess(setup, checkout)
                self.assertIn("runs-on: ubuntu-24.04", source)
                self.assertIn("permissions:\n  contents: read\n", source)
                for command in SETUP:
                    self.assertIn(command, setup_block)
                self.assertNotIn("scripts/", setup_block)
                self.assertNotIn("sysctl", setup_block)
                self.assertNotIn("apparmor_parser -R", setup_block)

    def test_existing_namespace_test_keeps_unshare_all(self):
        source = (ROOT / "tests/test_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"--unshare-all"', source)
        self.assertIn('"--ro-bind"', source)


if __name__ == "__main__":
    unittest.main()
