"""Focused doctor --install compatibility checks for Prodex 0.166.1."""

import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "d9c3232ca504548c473ad06e4be001bb307256e00d35f888676e9512c62e4c3a"
ORACLE_VERSION = "prodex 0.166.1\n"


def environment(root, path):
    home = root / "home"
    return {
        "HOME": str(home),
        "PATH": path,
        "TMPDIR": str(root),
        "TERM": "dumb",
        "NO_COLOR": "1",
        "TZ": "UTC",
        "PRODEX_HOME": str(root / "prodex-home"),
        "PRODEX_SHARED_CODEX_HOME": str(root / "shared-codex"),
        "PRODEX_OPTIMIZERS_HOME": str(root / "managed-tools"),
        "PRODEX_TERM_COLUMNS": "120",
        "OPENAI_API_KEY": "synthetic-provider-key",
    }


def run_doctor(binary, root, env):
    system_tools = (Path("/bin/sh").resolve(),)
    command = sandbox_command(
        binary, root, ["doctor", "--install"], environment=env,
        extra_binaries=system_tools,
    )
    separator = command.index("--")
    command[separator:separator] = ["--ro-bind", str(system_tools[0]), "/bin/sh"]
    return subprocess.run(
        command, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=30, check=False,
    )


def add_probe(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o700)
    return path


class DoctorInstall01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (
            not ORACLE.is_file()
            or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.1 release")
        with tempfile.TemporaryDirectory(prefix="modex-doctor-version-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            home.mkdir(mode=0o700)
            version = subprocess.run(
                [str(ORACLE), "--version"], cwd=root,
                env={
                    "HOME": str(home), "PATH": "", "TMPDIR": str(root),
                    "TERM": "dumb", "NO_COLOR": "1", "TZ": "UTC",
                },
                capture_output=True, text=True, timeout=10, check=False,
            )
            if (version.returncode, version.stdout, version.stderr) != (0, ORACLE_VERSION, ""):
                raise AssertionError("PRODEX_ORACLE must report the verified 0.166.1 release")
            if list(home.iterdir()):
                raise AssertionError("Prodex --version created state in the isolated home")

    def test_missing_automatic_tool_inventory_matches_01661_without_state(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-01661-") as raw:
            root = Path(raw)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            (root / "managed-tools").mkdir(mode=0o700)
            env = environment(root, "")

            baseline = run_doctor(ORACLE, root, env)
            modex = run_doctor(MODEX, root, env)

            self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
            self.assertEqual(
                baseline.stdout.replace(str(root).encode(), b"<scratch>"),
                modex.stdout.replace(str(root).encode(), b"<scratch>"),
            )
            self.assertEqual(modex.stderr, baseline.stderr)
            for row in (
                b"rtk:", b"codebase-memory-mcp:", b"playwright-mcp:", b"ponytail:",
            ):
                self.assertIn(row, modex.stdout)
            self.assertNotIn(b"Caveman:", modex.stdout)
            self.assertNotIn(b"synthetic-provider-key", modex.stdout)
            self.assertEqual(list((root / "home").iterdir()), [])

    def test_playwright_probe_is_no_install_and_managed_ponytail_is_not_executed(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-safe-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            managed = root / "managed-tools"
            for directory in (home, workspace, bindir, managed):
                directory.mkdir(mode=0o700)

            marker = root / "ponytail-executed"
            outside = add_probe(
                root,
                "outside-ponytail",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n",
            )
            (managed / "ponytail").symlink_to(outside)
            probe_log = root / "npx-arguments.log"
            add_probe(bindir, "node", "printf 'vvvv18.0.0\\n'\n")
            add_probe(
                bindir,
                "npx",
                f"printf '%s\\n' \"$*\" >> {shlex.quote(str(probe_log))}\n"
                "if [ \"$*\" = '--version' ]; then printf 'npx 10.9.0\\n'; exit 0; fi\n"
                "if [ \"$*\" = '--no-install @playwright/mcp --version' ]; then "
                "printf 'Authorization: Bearer synthetic-playwright-token \\033[31m@playwright/mcp 0.0.83 \\033[0m\\n'; exit 0; fi\n"
                "exit 64\n",
            )
            env = environment(root, str(bindir))

            baseline = run_doctor(ORACLE, root, env)
            self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
            self.assertIn(b"playwright-mcp:", baseline.stdout)
            self.assertIn(b"ponytail:", baseline.stdout)
            self.assertIn(
                "--no-install @playwright/mcp --version",
                probe_log.read_text().splitlines(),
            )
            self.assertFalse(marker.exists(), "Prodex must reject an escaping managed tool")
            probe_log.unlink()

            result = run_doctor(MODEX, root, env)

            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertIn(b"ok (Authorization: Bearer <redacted>", result.stdout)
            self.assertIn(b"@playwright/mcp 0.0.83", result.stdout)
            self.assertIn(
                b"degraded (managed Ponytail found; plugin-tree validation is unavailable)",
                result.stdout,
            )
            self.assertNotIn(b"synthetic-playwright-token", result.stdout)
            self.assertNotIn(b"\x1b", result.stdout)
            self.assertEqual(
                probe_log.read_text().splitlines(),
                ["--version", "--no-install @playwright/mcp --version"],
            )
            self.assertFalse(marker.exists(), "Doctor must not execute an escaping managed tool")
            self.assertFalse((home / ".codex").exists())
            self.assertNotIn(b"synthetic-provider-key", result.stdout)

    def test_playwright_rejects_old_and_unrecognized_versions(self):
        cases = (
            (
                "old package",
                "@playwright/mcp 0.0.78",
                b"skipped (playwright-mcp 0.0.78 is too old;",
                None,
            ),
            (
                "unrecognized package",
                "Authorization: Bearer synthetic-invalid-playwright-token \\033[31mnot-a-version\\033[0m",
                b"missing (unrecognized Playwright MCP version)",
                b"synthetic-invalid-playwright-token",
            ),
        )
        for label, package_output, expected, secret in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="modex-doctor-playwright-version-01661-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                bindir = root / "bin"
                managed = root / "managed-tools"
                for directory in (home, workspace, bindir, managed):
                    directory.mkdir(mode=0o700)

                probe_log = root / "npx-arguments.log"
                add_probe(bindir, "node", "printf 'vv18.0.0\\n'\n")
                add_probe(
                    bindir,
                    "npx",
                    f"printf '%s\\n' \"$*\" >> {shlex.quote(str(probe_log))}\n"
                    "if [ \"$*\" = '--version' ]; then printf 'npx 10.9.0\\n'; exit 0; fi\n"
                    f"printf '%b\\n' {shlex.quote(package_output)}\n"
                    "exit 0\n",
                )
                result = run_doctor(MODEX, root, environment(root, str(bindir)))

                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                self.assertIn(expected, result.stdout)
                self.assertNotIn(b"ok (Authorization:", result.stdout)
                if secret:
                    self.assertNotIn(secret, result.stdout)
                self.assertNotIn(b"\x1b", result.stdout)
                self.assertEqual(
                    probe_log.read_text().splitlines(),
                    ["--version", "--no-install @playwright/mcp --version"],
                )

    def test_unsupported_or_invalid_node_skips_package_probe(self):
        cases = (
            ("node 17", "printf 'v17.9.1\\n'\nexit 0\n"),
            ("invalid UTF-8", "printf '\\377\\n'\nexit 0\n"),
            ("nonzero exit", "printf 'v18.0.0\\n'\nexit 7\n"),
        )
        for label, node_probe in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="modex-doctor-node-guard-01661-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                bindir = root / "bin"
                managed = root / "managed-tools"
                for directory in (home, workspace, bindir, managed):
                    directory.mkdir(mode=0o700)

                node_log = root / "node-arguments.log"
                npx_log = root / "npx-arguments.log"
                package_marker = root / "playwright-probed"
                add_probe(
                    bindir,
                    "node",
                    f"printf '%s\\n' \"$*\" >> {shlex.quote(str(node_log))}\n"
                    + node_probe,
                )
                add_probe(
                    bindir,
                    "npx",
                    f"printf '%s\\n' \"$*\" >> {shlex.quote(str(npx_log))}\n"
                    "if [ \"$*\" = '--version' ]; then printf 'npx 10.9.0\\n'; exit 0; fi\n"
                    f"printf 'executed\\n' > {shlex.quote(str(package_marker))}\n"
                    "exit 0\n",
                )
                env = environment(root, str(bindir))

                for binary in (ORACLE, MODEX):
                    result = run_doctor(binary, root, env)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                    node_calls = node_log.read_text().splitlines()
                    self.assertGreaterEqual(len(node_calls), 2)
                    self.assertTrue(all(call == "--version" for call in node_calls))
                    if binary == MODEX:
                        self.assertEqual(len(node_calls), 2)
                    self.assertEqual(npx_log.read_text().splitlines(), ["--version"])
                    self.assertFalse(package_marker.exists(), f"{label} must skip package probing")
                    node_log.unlink()
                    npx_log.unlink()


if __name__ == "__main__":
    unittest.main()
