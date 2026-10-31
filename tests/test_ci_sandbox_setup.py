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

    def test_active_websocket_probe_uses_private_bwrap_network_namespace(self):
        runner = (ROOT / "scripts/ci/run_local_relay_websocket_fallback_01662.py").read_text(
            encoding="utf-8"
        )
        sandbox = (ROOT / "scripts/ci/run_websocket_fallback_01660.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("sandbox.bwrap_command(", runner)
        self.assertIn('"MODEX_REAL_CODEX_NETNS": "1"', runner)
        self.assertNotIn('shutil.which("unshare")', runner)
        self.assertNotIn("MODEX_LOCAL_RELAY_NETNS_READY", runner)
        self.assertNotIn('"--share-net"', runner)
        self.assertIn('"--unshare-all"', sandbox)
        self.assertIn('"--tmpfs", "/tmp"', sandbox)
        self.assertIn('"--uid", "0"', sandbox)
        self.assertIn('"--gid", "0"', sandbox)


if __name__ == "__main__":
    unittest.main()
