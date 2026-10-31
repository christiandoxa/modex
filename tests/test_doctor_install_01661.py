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
    "PRODEX_ORACLE_01661",
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


def run_doctor(binary, root, env, extra_binds=()):
    system_tools = (Path("/bin/sh").resolve(),)
    command = sandbox_command(
        binary, root, ["doctor", "--install"], environment=env,
        extra_binaries=system_tools,
    )
    separator = command.index("--")
    for source, destination in extra_binds:
        command[separator:separator] = ["--bind", str(source), destination]
        separator += 3
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


def panel_value(output, label):
    prefix = label.encode() + b":"
    rows = [line for line in output.splitlines() if line.startswith(prefix)]
    if len(rows) != 1:
        raise AssertionError(f"expected one {label} panel row, found {len(rows)}")
    return rows[0].split(b":", 1)[1].strip()


class DoctorInstall01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (
            not ORACLE.is_file()
            or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE_01661 must identify the verified 0.166.1 release")
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
                raise AssertionError("PRODEX_ORACLE_01661 must report the verified 0.166.1 release")
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

    def test_empty_managed_optimizer_home_does_not_probe_current_directory(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-empty-root-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            empty_path = root / "empty-path"
            for directory in (home, workspace, empty_path):
                directory.mkdir(mode=0o700)
            marker = root / "cwd-rtk-executed"
            add_probe(
                workspace,
                "rtk",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                "printf 'rtk 1.1.0\\n'\n",
            )
            env = environment(root, str(empty_path))
            env["PRODEX_OPTIMIZERS_HOME"] = ""

            baseline = run_doctor(ORACLE, root, env)
            self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(baseline.stdout, "rtk"), b"invalid")
            self.assertFalse(marker.exists())

            result = run_doctor(MODEX, root, env)

            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(result.stdout, "rtk"), b"invalid")
            self.assertFalse(
                marker.exists(),
                "an empty managed-root override must not turn the working directory into a probe root",
            )

    def test_empty_xdg_data_home_does_not_add_root_level_managed_directory(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-empty-xdg-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            empty_path = root / "empty-path"
            xdg_root = root / "absolute-xdg-tools"
            for directory in (home, workspace, empty_path, xdg_root):
                directory.mkdir(mode=0o700)
            marker = root / "empty-xdg-rtk-executed"
            add_probe(
                xdg_root,
                "rtk",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                "printf 'rtk 1.1.0\\n'\n",
            )
            env = environment(root, str(empty_path))
            env.pop("PRODEX_OPTIMIZERS_HOME")
            env["XDG_DATA_HOME"] = ""
            binds = ((xdg_root, "/prodex-optimizers"),)

            baseline = run_doctor(ORACLE, root, env, extra_binds=binds)
            self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(baseline.stdout, "rtk"), b"missing")
            self.assertFalse(marker.exists())

            result = run_doctor(MODEX, root, env, extra_binds=binds)

            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(result.stdout, "rtk"), b"missing")
            self.assertFalse(marker.exists(), "an empty XDG value must not create a root-level probe root")

    def test_trailing_slash_explicit_managed_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-root-slash-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            target = root / "outside-managed-root"
            empty_path = root / "empty-path"
            for directory in (home, workspace, target, empty_path):
                directory.mkdir(mode=0o700)
            marker = root / "rtk-executed"
            add_probe(
                target,
                "rtk",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                "printf 'rtk 1.1.0\\n'\n",
            )
            override = root / "managed-root-link"
            override.symlink_to(target, target_is_directory=True)
            env = environment(root, str(empty_path))
            env["PRODEX_OPTIMIZERS_HOME"] = str(override) + "/"

            baseline = run_doctor(ORACLE, root, env)
            self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(baseline.stdout, "rtk"), b"installed, version=rtk 1.1.0,")
            self.assertTrue(marker.exists(), "the reference fixture confirms the trailing-slash case")
            marker.unlink()

            result = run_doctor(MODEX, root, env)

            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(panel_value(result.stdout, "rtk"), b"invalid")
            self.assertFalse(marker.exists(), "Doctor must reject a symlinked explicit root before probing")

    def test_dot_components_do_not_hide_symlinked_managed_root_components(self):
        cases = (("dot", "/."), ("parent", "/.."))
        for label, suffix in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="modex-doctor-root-dot-01661-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                target = root / "outside-managed-root"
                empty_path = root / "empty-path"
                for directory in (home, workspace, target, empty_path):
                    directory.mkdir(mode=0o700)
                alias_target = target
                if suffix == "/..":
                    alias_target = target / "child"
                    alias_target.mkdir(mode=0o700)
                marker = root / "rtk-executed"
                add_probe(
                    target,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                    "printf 'rtk 1.1.0\\n'\n",
                )
                override = root / "managed-root-link"
                override.symlink_to(alias_target, target_is_directory=True)
                env = environment(root, str(empty_path))
                env["PRODEX_OPTIMIZERS_HOME"] = str(override) + suffix

                baseline = run_doctor(ORACLE, root, env)
                self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
                self.assertTrue(panel_value(baseline.stdout, "rtk").startswith(b"installed"))
                self.assertTrue(marker.exists(), "the reference fixture confirms the dot-component case")
                marker.unlink()

                result = run_doctor(MODEX, root, env)

                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                self.assertEqual(panel_value(result.stdout, "rtk"), b"invalid")
                self.assertFalse(marker.exists(), "a symlink path component must not reach the probe")

    def test_managed_probe_rejects_other_principal_write_access(self):
        cases = (
            ("private root", 0o700, 0o700, 0o700, b"installed, version=rtk 1.1.0,", True),
            ("writable root", 0o700, 0o777, 0o700, b"invalid", False),
            ("writable ancestor", 0o777, 0o700, 0o700, b"invalid", False),
            ("writable executable", 0o700, 0o700, 0o777, b"invalid", False),
            ("setuid executable", 0o700, 0o700, 0o4700, b"invalid", False),
            ("setgid executable", 0o700, 0o700, 0o2700, b"invalid", False),
        )
        for label, parent_mode, root_mode, executable_mode, expected, should_run in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix="modex-doctor-managed-permissions-01661-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                parent = root / "managed-parent"
                managed = parent / "managed-tools"
                for directory in (home, workspace, parent, managed):
                    directory.mkdir(mode=0o700)
                parent.chmod(parent_mode)
                managed.chmod(root_mode)
                marker = root / "rtk-executed"
                executable = add_probe(
                    managed,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                    "printf 'rtk 1.1.0\\n'\n",
                )
                executable.chmod(executable_mode)
                if executable_mode & 0o6000:
                    self.assertEqual(executable.stat().st_mode & 0o6000, executable_mode & 0o6000)
                env = environment(root, str(managed))
                env["PRODEX_OPTIMIZERS_HOME"] = str(managed)

                result = run_doctor(MODEX, root, env)

                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                status = panel_value(result.stdout, "rtk")
                if label == "private root":
                    self.assertTrue(status.startswith(expected))
                else:
                    self.assertEqual(status, expected)
                self.assertEqual(marker.exists(), should_run)

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
            self.assertIn(b"installed, version=Authorization: Bearer <redacted>", result.stdout)
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

    def test_escaping_managed_optional_commands_are_not_probed(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-managed-escape-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            managed = root / "managed-tools"
            for directory in (home, workspace, managed):
                directory.mkdir(mode=0o700)

            markers = {}
            for command, script, version in (
                ("rtk", "outside-rtk", "rtk 1.1.0"),
                (
                    "codebase-memory-mcp",
                    "outside-codebase-memory-mcp",
                    "codebase-memory-mcp 0.9.1",
                ),
            ):
                marker = root / f"{command}-executed"
                outside = add_probe(
                    root,
                    script,
                    f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                    f"printf '{version}\\n'\n",
                )
                (managed / command).symlink_to(outside)
                markers[command] = marker

            env = environment(root, str(managed))
            baseline = run_doctor(ORACLE, root, env)
            self.assertEqual(baseline.returncode, 0, baseline.stderr.decode(errors="replace"))
            for command in markers:
                self.assertEqual(panel_value(baseline.stdout, command), b"invalid")
            self.assertFalse(any(marker.exists() for marker in markers.values()))

            result = run_doctor(MODEX, root, env)

            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            for command in markers:
                self.assertEqual(panel_value(result.stdout, command), b"invalid")
            self.assertFalse(
                any(marker.exists() for marker in markers.values()),
                "Doctor must not probe an optional command that escapes its managed root",
            )

    def test_playwright_rejects_old_and_unrecognized_versions(self):
        cases = (
            (
                "old package",
                "@playwright/mcp 0.0.78",
                b"invalid",
                None,
            ),
            (
                "unrecognized package",
                "Authorization: Bearer synthetic-invalid-playwright-token \\033[31mnot-a-version\\033[0m",
                b"missing",
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
