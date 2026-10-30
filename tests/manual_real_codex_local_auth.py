"""Exercise real Codex with isolated local Modex fixtures and no external route."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


MODEX = Path(os.environ.get("MODEX_BINARY", ""))
CODEX = Path(os.environ.get("CODEX_BINARY", ""))
NODE_BIN = Path(os.environ.get("NODE_BIN", Path.home() / ".local/share/upkit/node/active/bin"))
EXPECTED_VERSION = os.environ.get("MODEX_EXPECTED_CODEX_VERSION", "0.166.0")


class RealCodexLocalAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Set MODEX_BINARY to the candidate Modex executable")
        if not CODEX.is_file():
            raise AssertionError("Set CODEX_BINARY to the pinned Codex CLI")
        if os.environ.get("MODEX_REAL_CODEX_NETNS") != "1":
            raise AssertionError("Run under unshare -Urn to disable external network access")

        ip = shutil.which("ip")
        if not ip:
            raise AssertionError("iproute2 is required to enable loopback in the isolated network namespace")
        subprocess.run([ip, "link", "set", "lo", "up"], check=True, capture_output=True)
        links = subprocess.run([ip, "-o", "link", "show"], check=True, text=True,
                               capture_output=True).stdout.splitlines()
        interfaces = sorted(line.split(":", 2)[1].strip().split("@", 1)[0] for line in links)
        if interfaces != ["lo"]:
            raise AssertionError(f"network namespace has non-loopback interfaces: {interfaces}")
        routes = subprocess.run([ip, "route", "show", "default"], check=True, text=True,
                                capture_output=True).stdout.strip()
        if routes:
            raise AssertionError(f"network namespace has a default route: {routes}")
        routes_v6 = subprocess.run([ip, "-6", "route", "show", "default"], check=True, text=True,
                                   capture_output=True).stdout.strip()
        if routes_v6:
            raise AssertionError(f"network namespace has an IPv6 default route: {routes_v6}")

        cls.root = tempfile.TemporaryDirectory(prefix="modex-real-codex-auth-", dir="/tmp")
        cls.root_path = Path(cls.root.name)
        version_home = cls.root_path / "version-home"
        version_codex_home = version_home / ".codex"
        version_codex_home.mkdir(parents=True, mode=0o700)
        version_env = {
            "HOME": str(version_home),
            "CODEX_HOME": str(version_codex_home),
            "PATH": f"{NODE_BIN}:/usr/bin:/bin",
        }
        version = subprocess.run([str(CODEX), "--version"], env=version_env,
                                 capture_output=True, text=True, timeout=10)
        version_line = re.compile(r"(?m)^codex-cli " + re.escape(EXPECTED_VERSION) + r"$")
        if version.returncode != 0 or not version_line.search(version.stdout + version.stderr):
            raise AssertionError(f"expected Codex {EXPECTED_VERSION}: {version.stdout!r} {version.stderr!r}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "root"):
            cls.root.cleanup()

    def test_private_auth_token_authorizes_real_codex_request(self):
        from test_super_launch import SuperLaunchTests

        wrapper = self.root_path / "codex-auth-capture"
        token_capture = self.root_path / "captured-auth.jsonl"
        wrapper.write_text(
            "#!/usr/bin/python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "home = os.environ.get('CODEX_HOME')\n"
            "auth_path = Path(home) / 'auth.json' if home else None\n"
            "if auth_path and auth_path.is_file():\n"
            "    auth = json.loads(auth_path.read_text())\n"
            "    with open(os.environ['MODEX_AUTH_CAPTURE'], 'a', encoding='utf-8') as out:\n"
            "        out.write(json.dumps({'token': auth['OPENAI_API_KEY'], 'mode': auth.get('auth_mode')}) + '\\n')\n"
            "os.execv(os.environ['MODEX_REAL_CODEX'], [os.environ['MODEX_REAL_CODEX'], *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)

        result, _, upstream, state = SuperLaunchTests().run_launch(
            MODEX,
            scenario="stream",
            temporary_directory=self.root_path,
            codex_binary=wrapper,
            codex_arguments=(
                "exec", "--ephemeral", "--skip-git-repo-check", "--json", "--",
                "Reply with the synthetic provider response.",
            ),
            environment_overrides={
                "PATH": f"{NODE_BIN}:/usr/bin:/bin",
                "MODEX_REAL_CODEX": str(CODEX),
                "MODEX_AUTH_CAPTURE": str(token_capture),
                "OPENAI_API_KEY": "synthetic-wrong-openai-key",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertTrue(all(Path(path).is_relative_to(self.root_path) for path in state["leftovers"]))
        self.assertEqual(len(upstream), 1)
        self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
        authorization = next(value for key, value in upstream[0]["headers"].items()
                             if key.lower() == "authorization")
        self.assertEqual(authorization, "Bearer synthetic-provider-key")
        self.assertTrue(token_capture.is_file())
        captured = [json.loads(line) for line in token_capture.read_text().splitlines()]
        self.assertTrue(captured)
        tokens = {record["token"] for record in captured}
        self.assertEqual(len(tokens), 1)
        token = tokens.pop()
        self.assertRegex(token, re.compile(r"^[0-9a-f]{64}$"))
        self.assertEqual({record["mode"] for record in captured}, {"apikey"})
        self.assertNotIn(token.encode(), result.stdout + result.stderr)
        self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
