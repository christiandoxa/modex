"""Compare the read-only doctor --install inventory with Prodex 0.166.2."""

import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


def environment(root, path):
    return {
        "PATH": str(path),
        "TMPDIR": str(root),
        "PRODEX_HOME": str(root / "prodex-home"),
        "PRODEX_SHARED_CODEX_HOME": str(root / "shared-codex"),
        "PRODEX_OPTIMIZERS_HOME": str(root / "managed-tools"),
        "PRODEX_TERM_COLUMNS": "120",
    }


def run_doctor(binary, root, env, extra_binds=()):
    shell = Path("/bin/sh").resolve()
    command = sandbox_command(
        binary,
        root,
        ["doctor", "--install"],
        environment=env,
        extra_binaries=(shell,),
    )
    separator = command.index("--")
    for source, destination in extra_binds:
        command[separator:separator] = ["--bind", str(source), destination]
        separator += 3
    command[separator:separator] = ["--ro-bind", str(shell), "/bin/sh"]
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )


def add_probe(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o700)
    return path


def codebase_probe(log, leaked_environment, version_body, version_exit, daemon_body, daemon_exit):
    return (
        f"if [ \"${{SYNTHETIC_PROBE_SECRET-}}\" = 'synthetic-doctor-probe-secret' ]; then "
        f"printf 'leaked\\n' > {shlex.quote(str(leaked_environment))}; fi\n"
        f"if [ \"${{XDG_CONFIG_HOME-}}\" = 'synthetic-codebase-xdg-config' ]; then "
        f"printf 'leaked\\n' > {shlex.quote(str(leaked_environment))}; fi\n"
        f"printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}\n"
        "if [ \"$1\" = '--version' ]; then\n"
        + version_body
        + f"exit {version_exit}\nfi\n"
        "if [ \"$1\" = 'daemon' ] && [ \"$2\" = 'status' ]; then\n"
        + daemon_body
        + f"exit {daemon_exit}\nfi\n"
        "exit 64\n"
    )


def panel_value(output, label):
    prefix = label.encode() + b":"
    rows = [line for line in output.splitlines() if line.startswith(prefix)]
    if len(rows) != 1:
        raise AssertionError(f"expected one {label} panel row, found {len(rows)}")
    return rows[0].split(b":", 1)[1].strip()


def paths(root):
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


def normalized(root, output):
    return output.replace(str(root).encode(), b"<scratch>")


class DoctorInstall01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if (
            not ORACLE.is_file()
            or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_missing_tool_inventory_matches_without_state(self):
        results = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="doctor-install-empty-01662-") as raw:
                root = Path(raw)
                home = root / "home"
                home.mkdir(mode=0o700)
                (root / "workspace").mkdir()
                (root / "managed-tools").mkdir(mode=0o700)
                before = paths(root)

                result = run_doctor(binary, root, environment(root, ""))

                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(paths(root), before)
                self.assertIn(b"Codex CLI:           missing", result.stdout)
                self.assertIn(b"playwright-mcp:      missing", result.stdout)
                self.assertIn(b"ponytail:            missing", result.stdout)
                results.append((result.returncode, normalized(root, result.stdout), result.stderr))
        self.assertEqual(results[0], results[1])

    def test_rtk_and_playwright_install_details_match_without_cwd_probe(self):
        for placement in ("managed", "path"):
            with self.subTest(placement=placement), tempfile.TemporaryDirectory(
                prefix="doctor-install-details-01662-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                bindir = root / "bin"
                managed = root / "managed-tools"
                for directory in (home, workspace, bindir, managed):
                    directory.mkdir(mode=0o700)

                rtk_marker = root / "selected-rtk-executed"
                cwd_marker = root / "cwd-rtk-executed"
                probe_log = root / "npx-arguments.log"
                target = managed if placement == "managed" else bindir
                add_probe(
                    target,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(rtk_marker))}\n"
                    "printf 'rtk 1.0.0\\n'\n",
                )
                add_probe(
                    workspace,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(cwd_marker))}\n"
                    "printf 'rtk cwd\\n'\n",
                )
                add_probe(bindir, "node", "printf 'v18.0.0\\n'\n")
                add_probe(
                    bindir,
                    "npx",
                    f"printf '%s\\n' \"$*\" >> {shlex.quote(str(probe_log))}\n"
                    "if [ \"$*\" = '--version' ]; then printf '%s\\n' 'npx 10.9.0'; exit 0; fi\n"
                    "if [ \"$*\" = '--no-install @playwright/mcp --version' ]; then "
                    "printf '%s\\n' '@playwright/mcp 0.0.83'; exit 0; fi\n"
                    "exit 64\n",
                )
                env = environment(root, bindir)
                env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
                before = paths(root)

                reference = run_doctor(ORACLE, root, env)
                self.assertEqual((reference.returncode, reference.stderr), (0, b""))
                self.assertTrue(panel_value(reference.stdout, "rtk").startswith(b"installed, version="))
                self.assertTrue(
                    panel_value(reference.stdout, "playwright-mcp").startswith(b"installed, version=")
                )
                self.assertTrue(rtk_marker.exists())
                self.assertFalse(cwd_marker.exists())
                self.assertEqual(
                    probe_log.read_text(encoding="utf-8").splitlines(),
                    ["--version", "--no-install @playwright/mcp --version"],
                )
                expected = normalized(root, reference.stdout)
                rtk_marker.unlink()
                probe_log.unlink()

                actual = run_doctor(MODEX, root, env)
                self.assertEqual((actual.returncode, actual.stderr), (0, b""))
                self.assertEqual(normalized(root, actual.stdout), expected)
                self.assertTrue(rtk_marker.exists())
                self.assertFalse(cwd_marker.exists())
                self.assertEqual(
                    probe_log.read_text(encoding="utf-8").splitlines(),
                    ["--version", "--no-install @playwright/mcp --version"],
                )
                rtk_marker.unlink()
                probe_log.unlink()
                self.assertEqual(paths(root), before)
                self.assertFalse((home / ".codex").exists())

    def test_invalid_playwright_versions_match_reference(self):
        cases = (
            ("old", "@playwright/mcp 0.0.78", b"invalid"),
            (
                "unrecognized",
                "Authorization: Bearer synthetic-playwright-token \\033[31mnot-a-version\\033[0m",
                b"missing",
            ),
        )
        for name, package_output, expected_status in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix="doctor-install-playwright-version-01662-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                bindir = root / "bin"
                managed = root / "managed-tools"
                for directory in (home, workspace, bindir, managed):
                    directory.mkdir(mode=0o700)
                probe_log = root / "npx-arguments.log"
                add_probe(bindir, "node", "printf 'v18.0.0\\n'\n")
                add_probe(
                    bindir,
                    "npx",
                    f"printf '%s\\n' \"$*\" >> {shlex.quote(str(probe_log))}\n"
                    "if [ \"$*\" = '--version' ]; then printf '%s\\n' 'npx 10.9.0'; exit 0; fi\n"
                    "if [ \"$*\" = '--no-install @playwright/mcp --version' ]; then "
                    f"printf '%s\\n' '{package_output}'; exit 0; fi\n"
                    "exit 64\n",
                )
                env = environment(root, bindir)
                env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
                before = paths(root)

                reference = run_doctor(ORACLE, root, env)
                self.assertEqual((reference.returncode, reference.stderr), (0, b""))
                self.assertEqual(panel_value(reference.stdout, "playwright-mcp"), expected_status)
                self.assertEqual(
                    probe_log.read_text(encoding="utf-8").splitlines(),
                    ["--version", "--no-install @playwright/mcp --version"],
                )
                expected = normalized(root, reference.stdout)
                probe_log.unlink()

                actual = run_doctor(MODEX, root, env)
                self.assertEqual((actual.returncode, actual.stderr), (0, b""))
                self.assertEqual(panel_value(actual.stdout, "playwright-mcp"), expected_status)
                self.assertEqual(normalized(root, actual.stdout), expected)
                self.assertEqual(
                    probe_log.read_text(encoding="utf-8").splitlines(),
                    ["--version", "--no-install @playwright/mcp --version"],
                )
                probe_log.unlink()
                self.assertEqual(paths(root), before)
                self.assertFalse((home / ".codex").exists())

    def test_invalid_managed_rtk_version_output_matches_reference(self):
        cases = (
            ("unrecognized", "printf '%s\\n' 'nonsense version output'\n"),
            ("ready", "printf '%s\\n' 'ready'\n"),
            ("too-old", "printf '%s\\n' 'rtk 0.45.0'\n"),
            ("invalid-utf8", "printf '\\377\\n'\n"),
            ("nonzero", "printf '%s\\n' 'rtk 1.0.0'\nexit 7\n"),
            ("empty", "exit 0\n"),
        )
        for name, body in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix="doctor-install-invalid-rtk-01662-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                empty_path = root / "empty-path"
                managed = root / "managed-tools"
                for directory in (home, workspace, empty_path, managed):
                    directory.mkdir(mode=0o700)
                marker = root / "managed-rtk-executed"
                add_probe(
                    managed,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(marker))}\n" + body,
                )
                env = environment(root, empty_path)
                env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
                before = paths(root)

                reference = run_doctor(ORACLE, root, env)
                self.assertEqual((reference.returncode, reference.stderr), (0, b""))
                self.assertEqual(panel_value(reference.stdout, "rtk"), b"invalid")
                self.assertTrue(marker.exists())
                marker.unlink()

                actual = run_doctor(MODEX, root, env)
                self.assertEqual((actual.returncode, actual.stderr), (0, b""))
                self.assertEqual(panel_value(actual.stdout, "rtk"), b"invalid")
                self.assertEqual(normalized(root, actual.stdout), normalized(root, reference.stdout))
                self.assertTrue(marker.exists())
                marker.unlink()
                self.assertEqual(paths(root), before)

    def test_installed_path_and_version_escape_controls_and_redact_secrets(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-redaction-01662-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            empty_path = root / "empty-path"
            managed = root / "managed-\x1b[31m-Authorization: Bearer synthetic-doctor-path-token"
            for directory in (home, workspace, empty_path, managed):
                directory.mkdir(mode=0o700)
            add_probe(
                managed,
                "rtk",
                "printf 'rtk 1.0.0 Authorization: Bearer synthetic-doctor-version-token "
                "\\033[31m\\n'\n",
            )
            env = environment(root, empty_path)
            env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
            env["PRODEX_TERM_COLUMNS"] = "4096"
            before = paths(root)

            reference = run_doctor(ORACLE, root, env)
            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            actual = run_doctor(MODEX, root, env)
            self.assertEqual((actual.returncode, actual.stderr), (0, b""))
            expected = normalized(root, reference.stdout).replace(b"\x1b", b"\\x1b")
            output = normalized(root, actual.stdout)
            self.assertEqual(output, expected)
            self.assertNotIn(b"synthetic-doctor-path-token", output)
            self.assertNotIn(b"synthetic-doctor-version-token", output)
            self.assertNotIn(b"\x1b", output)
            self.assertIn(b"Authorization: Bearer <redacted>", output)
            self.assertIn(b"\\x1b[31m", output)
            self.assertEqual(paths(root), before)

    def test_empty_xdg_data_home_does_not_probe_root_level_tool_path(self):
        results = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="doctor-install-xdg-01662-") as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                empty_path = root / "empty-path"
                xdg_tools = root / "xdg-tools"
                for directory in (home, workspace, empty_path, xdg_tools):
                    directory.mkdir(mode=0o700)
                marker = root / "root-level-rtk-executed"
                add_probe(
                    xdg_tools,
                    "rtk",
                    f"printf 'executed\\n' > {shlex.quote(str(marker))}\n",
                )
                env = environment(root, empty_path)
                env.pop("PRODEX_OPTIMIZERS_HOME")
                env["XDG_DATA_HOME"] = ""
                before = paths(root)

                result = run_doctor(
                    binary,
                    root,
                    env,
                    extra_binds=((xdg_tools, "/prodex-optimizers"),),
                )

                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(panel_value(result.stdout, "rtk"), b"missing")
                self.assertFalse(marker.exists())
                self.assertEqual(paths(root), before)
                results.append((result.returncode, normalized(root, result.stdout), result.stderr))
        self.assertEqual(results[0], results[1])

    def test_empty_managed_root_does_not_turn_working_directory_into_probe_path(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-empty-root-01662-") as raw:
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
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n",
            )
            env = environment(root, empty_path)
            env["PRODEX_OPTIMIZERS_HOME"] = ""

            reference = run_doctor(ORACLE, root, env)
            actual = run_doctor(MODEX, root, env)

            self.assertEqual((reference.returncode, actual.returncode), (0, 0))
            self.assertEqual(panel_value(reference.stdout, "rtk"), b"invalid")
            self.assertEqual(panel_value(actual.stdout, "rtk"), b"missing")
            self.assertFalse(marker.exists())
            self.assertFalse((home / ".codex").exists())

    def test_playwright_is_no_install_and_escaping_ponytail_is_not_run(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-no-install-01662-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            managed = root / "managed-tools"
            for directory in (home, workspace, bindir, managed):
                directory.mkdir(mode=0o700)

            ponytail_marker = root / "ponytail-executed"
            outside = add_probe(
                root,
                "outside-ponytail",
                f"printf 'executed\\n' > {shlex.quote(str(ponytail_marker))}\n",
            )
            (managed / "ponytail").symlink_to(outside)
            probe_log = root / "npx-arguments.log"
            add_probe(bindir, "node", "printf 'v18.0.0\\n'\n")
            add_probe(
                bindir,
                "npx",
                f"printf '%s\\n' \"$*\" >> {shlex.quote(str(probe_log))}\n"
                "if [ \"$*\" = '--version' ]; then printf 'npx 10.9.0\\n'; exit 0; fi\n"
                "if [ \"$*\" = '--no-install @playwright/mcp --version' ]; then "
                "printf 'Authorization: Bearer synthetic-playwright-token "
                "\\033[31m@playwright/mcp 0.0.83 \\033[0m\\n'; exit 0; fi\n"
                "exit 64\n",
            )
            env = environment(root, bindir)
            env["PRODEX_OPTIMIZERS_HOME"] = str(managed)

            reference = run_doctor(ORACLE, root, env)
            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            self.assertEqual(
                probe_log.read_text(encoding="utf-8").splitlines(),
                ["--version", "--no-install @playwright/mcp --version"],
            )
            self.assertFalse(ponytail_marker.exists())
            probe_log.unlink()

            actual = run_doctor(MODEX, root, env)

            self.assertEqual((actual.returncode, actual.stderr), (0, b""))
            self.assertEqual(
                probe_log.read_text(encoding="utf-8").splitlines(),
                ["--version", "--no-install @playwright/mcp --version"],
            )
            self.assertIn(b"@playwright/mcp 0.0.83", actual.stdout)
            self.assertNotIn(b"synthetic-playwright-token", actual.stdout)
            self.assertNotIn(b"\x1b", actual.stdout)
            self.assertFalse(ponytail_marker.exists())
            self.assertFalse((home / ".codex").exists())

    def test_codebase_memory_requires_supported_version_and_daemon_health(self):
        def output_line(value, channel="stdout"):
            redirection = " >&2" if channel == "stderr" else ""
            return f"printf '%s\\n' {shlex.quote(value)}{redirection}\n"

        def invalid_utf8(channel="stdout"):
            redirection = " >&2" if channel == "stderr" else ""
            return "printf '\\377\\n'" + redirection + "\n"

        cases = (
            (
                "active",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line("daemon: active (permanent)"),
                0,
                True,
                True,
                ("path", "managed"),
            ),
            (
                "initially-stopped",
                output_line("codebase-memory-mcp 0.9.1-rc.1", "stderr"),
                0,
                output_line("daemon: not running", "stderr"),
                1,
                True,
                True,
                ("path", "managed"),
            ),
            (
                "dev-version",
                output_line("codebase-memory-mcp dev"),
                0,
                output_line("daemon: active-other"),
                0,
                True,
                True,
                ("path",),
            ),
            (
                "version-secret-redacted",
                output_line("codebase-memory-mcp 0.12.1+sk-ant-api03-secretsecret"),
                0,
                output_line("daemon: active (permanent)"),
                0,
                True,
                True,
                ("path",),
            ),
            (
                "active-nonzero",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line("daemon: active (permanent)"),
                7,
                False,
                True,
                ("path", "managed"),
            ),
            (
                "malformed-daemon",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line("usage: daemon <command>"),
                0,
                False,
                True,
                ("path",),
            ),
            (
                "malformed-json-daemon",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line('{"status":"daemon: active (permanent)"}'),
                0,
                False,
                True,
                ("path",),
            ),
            (
                "daemon-output-is-not-displayed",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line("daemon: active \x1b[31mAuthorization: Bearer synthetic-codebase-probe-token"),
                0,
                True,
                True,
                ("path",),
            ),
            (
                "unsupported-version",
                output_line("codebase-memory-mcp 0.9.0"),
                0,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "below-prerelease-floor",
                output_line("codebase-memory-mcp 0.9.1-rc.0"),
                0,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "version-failed",
                output_line("codebase-memory-mcp 0.12.1"),
                7,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "empty-version",
                "",
                0,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "invalid-version-stdout-utf8",
                invalid_utf8(),
                0,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "invalid-version-stderr-utf8",
                output_line("codebase-memory-mcp 0.12.1") + invalid_utf8("stderr"),
                0,
                output_line("daemon: active (permanent)"),
                0,
                False,
                False,
                ("path",),
            ),
            (
                "invalid-daemon-stdout-utf8",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                invalid_utf8(),
                0,
                False,
                True,
                ("path",),
            ),
            (
                "invalid-daemon-stderr-utf8",
                output_line("codebase-memory-mcp 0.12.1"),
                0,
                output_line("daemon: active (permanent)") + invalid_utf8("stderr"),
                0,
                False,
                True,
                ("path",),
            ),
        )

        for name, version_body, version_exit, daemon_body, daemon_exit, installed, calls_daemon, placements in cases:
            for placement in placements:
                with self.subTest(name=name, placement=placement), tempfile.TemporaryDirectory(
                    prefix="doctor-install-codebase-01662-"
                ) as raw:
                    root = Path(raw)
                    home = root / "home"
                    workspace = root / "workspace"
                    bindir = root / "bin"
                    managed = root / "managed-tools"
                    for directory in (home, workspace, bindir, managed):
                        directory.mkdir(mode=0o700)
                    probe_log = root / "codebase-arguments.log"
                    probe_log.write_text("", encoding="utf-8")
                    leaked_environment = root / "probe-environment-leaked"
                    target = bindir if placement == "path" else managed
                    add_probe(
                        target,
                        "codebase-memory-mcp",
                        codebase_probe(
                            probe_log,
                            leaked_environment,
                            version_body,
                            version_exit,
                            daemon_body,
                            daemon_exit,
                        ),
                    )
                    env = environment(root, bindir)
                    env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
                    env["SYNTHETIC_PROBE_SECRET"] = "synthetic-doctor-probe-secret"
                    env["XDG_CONFIG_HOME"] = "synthetic-codebase-xdg-config"
                    before = paths(root)
                    expected_calls = ["--version"] + (["daemon status"] if calls_daemon else [])
                    expected_output = None

                    for binary in (ORACLE, MODEX):
                        probe_log.write_text("", encoding="utf-8")
                        result = run_doctor(binary, root, env)
                        self.assertEqual((result.returncode, result.stderr), (0, b""))
                        status = panel_value(result.stdout, "codebase-memory-mcp")
                        if installed:
                            self.assertTrue(status.startswith(b"installed, version="), status)
                        else:
                            self.assertEqual(status, b"invalid")
                        self.assertEqual(probe_log.read_text(encoding="utf-8").splitlines(), expected_calls)
                        self.assertFalse(leaked_environment.exists())
                        self.assertNotIn(b"synthetic-doctor-probe-secret", result.stdout)
                        self.assertNotIn(b"synthetic-codebase-probe-token", result.stdout)
                        self.assertNotIn(b"sk-ant-api03-secretsecret", result.stdout)
                        self.assertNotIn(b"\x1b", result.stdout)
                        output = normalized(root, result.stdout)
                        if binary == ORACLE:
                            expected_output = output
                        else:
                            self.assertEqual(output, expected_output)

                    self.assertEqual(paths(root), before)
                    self.assertFalse((home / ".codex").exists())

    def test_codebase_memory_working_directory_decoy_is_not_run(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-codebase-cwd-01662-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            empty_path = root / "empty-path"
            managed = root / "managed-tools"
            for directory in (home, workspace, empty_path, managed):
                directory.mkdir(mode=0o700)
            marker = root / "cwd-codebase-executed"
            add_probe(
                workspace,
                "codebase-memory-mcp",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                "printf 'codebase-memory-mcp 0.12.1\\n'\n",
            )
            env = environment(root, empty_path)
            env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
            before = paths(root)

            reference = run_doctor(ORACLE, root, env)
            actual = run_doctor(MODEX, root, env)

            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            self.assertEqual((actual.returncode, actual.stderr), (0, b""))
            self.assertEqual(panel_value(reference.stdout, "codebase-memory-mcp"), b"missing")
            self.assertEqual(panel_value(actual.stdout, "codebase-memory-mcp"), b"missing")
            self.assertEqual(normalized(root, actual.stdout), normalized(root, reference.stdout))
            self.assertFalse(marker.exists())
            self.assertEqual(paths(root), before)
            self.assertFalse((home / ".codex").exists())

    def test_codebase_memory_escaping_managed_symlink_is_not_run(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-codebase-escape-01662-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            empty_path = root / "empty-path"
            managed = root / "managed-tools"
            for directory in (home, workspace, empty_path, managed):
                directory.mkdir(mode=0o700)
            marker = root / "escaping-codebase-executed"
            outside = add_probe(
                workspace,
                "outside-codebase-memory-mcp",
                f"printf 'executed\\n' > {shlex.quote(str(marker))}\n"
                "printf 'codebase-memory-mcp 0.12.1\\n'\n",
            )
            (managed / "codebase-memory-mcp").symlink_to(outside)
            env = environment(root, empty_path)
            env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
            before = paths(root)

            reference = run_doctor(ORACLE, root, env)
            actual = run_doctor(MODEX, root, env)

            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            self.assertEqual((actual.returncode, actual.stderr), (0, b""))
            self.assertEqual(panel_value(reference.stdout, "codebase-memory-mcp"), b"invalid")
            self.assertEqual(panel_value(actual.stdout, "codebase-memory-mcp"), b"invalid")
            self.assertEqual(normalized(root, actual.stdout), normalized(root, reference.stdout))
            self.assertFalse(marker.exists())
            self.assertEqual(paths(root), before)
            self.assertFalse((home / ".codex").exists())

    def test_codebase_memory_over_cap_output_remains_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="doctor-install-codebase-output-limit-01662-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            managed = root / "managed-tools"
            for directory in (home, workspace, bindir, managed):
                directory.mkdir(mode=0o700)
            probe_log = root / "codebase-arguments.log"
            probe_log.write_text("", encoding="utf-8")
            add_probe(
                bindir,
                "codebase-memory-mcp",
                codebase_probe(
                    probe_log,
                    root / "probe-environment-leaked",
                    "printf '%s\\n' 'codebase-memory-mcp 0.12.1'\n",
                    0,
                    "printf '%s%70000s\\n' 'daemon: active (permanent)' ''\n",
                    0,
                ),
            )
            env = environment(root, bindir)
            env["PRODEX_OPTIMIZERS_HOME"] = str(managed)
            before = paths(root)

            reference = run_doctor(ORACLE, root, env)
            reference_calls = probe_log.read_text(encoding="utf-8").splitlines()
            probe_log.write_text("", encoding="utf-8")
            actual = run_doctor(MODEX, root, env)

            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            self.assertEqual((actual.returncode, actual.stderr), (0, b""))
            self.assertTrue(
                panel_value(reference.stdout, "codebase-memory-mcp").startswith(b"installed, version=")
            )
            self.assertEqual(panel_value(actual.stdout, "codebase-memory-mcp"), b"invalid")
            self.assertEqual(reference_calls, ["--version", "daemon status"])
            self.assertEqual(
                probe_log.read_text(encoding="utf-8").splitlines(),
                ["--version", "daemon status"],
            )
            self.assertLess(len(reference.stdout), 10000)
            self.assertLess(len(actual.stdout), 10000)
            self.assertEqual(paths(root), before)
            self.assertFalse((home / ".codex").exists())


if __name__ == "__main__":
    unittest.main()
