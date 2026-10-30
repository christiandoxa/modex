"""doctor --install process parity with the official 0.166.0 release."""

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
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


def probe_log_script(name, log_path):
    return (
        "if [ \"${SYNTHETIC_PROBE_SENTINEL-}\" = fixture-sentinel ]; then probe_secret=present; else probe_secret=absent; fi\n"
        "if [ -n \"${OPENAI_API_KEY-}\" ]; then provider_key=present; else provider_key=absent; fi\n"
        "if [ -n \"${CODEX_HOME-}\" ]; then codex_home=set; else codex_home=unset; fi\n"
        "if [ -n \"${PRODEX_HOME-}\" ]; then prodex_home=set; else prodex_home=unset; fi\n"
        "if [ -n \"${PRODEX_SHARED_CODEX_HOME-}\" ]; then shared_codex_home=set; else shared_codex_home=unset; fi\n"
        "if [ -n \"${PRODEX_OPTIMIZERS_HOME-}\" ]; then optimizers_home=set; else optimizers_home=unset; fi\n"
        f"printf '{name}\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$*\" \"$probe_secret\" \"$provider_key\" \"$codex_home\" \"$prodex_home\" \"$shared_codex_home\" \"$optimizers_home\" >> {shlex.quote(str(log_path))}\n"
    )


def add_probe(directory, name, log_path, stdout="", stderr="", exit_code=0):
    body = "#!/bin/sh\n" + probe_log_script(name, log_path)
    body += f"printf '%b' {stdout!r}\n" if stdout else ""
    body += f"printf '%b' {stderr!r} >&2\n" if stderr else ""
    body += f"exit {exit_code}\n"
    path = directory / name
    path.write_text(body)
    path.chmod(0o700)
    return path


def command_environment(root, path):
    home = root / "home"
    return {
        "HOME": str(home),
        "PATH": path,
        "TMPDIR": str(root),
        "TERM": "dumb",
        "NO_COLOR": "1",
        "PRODEX_HOME": str(root / "api_key=synthetic-prodex-path-secret\x1b[31m"),
        "PRODEX_SHARED_CODEX_HOME": str(root / "token=synthetic-shared-path-secret\x1b]0;fixture\x07"),
        "PRODEX_OPTIMIZERS_HOME": str(root / "auth_key=synthetic-optimizer-path-secret"),
        "CODEX_HOME": str(home / ".codex"),
        "PRODEX_TERM_COLUMNS": "120",
        "SYNTHETIC_PROBE_SENTINEL": "fixture-sentinel",
        "OPENAI_API_KEY": "synthetic-provider-key",
    }


def safer_modex_output(reference):
    output = reference
    for value in (
        b"Authorization: Bearer synthetic-secret-token",
        b"Authorization: Bearer synthetic-stderr-token",
        b"api_key=synthetic-prodex-path-secret",
        b"token=synthetic-shared-path-secret",
        b"api_key=synthetic-command-path-secret",
    ):
        key, _ = value.split(b"=", 1) if b"=" in value else (b"", b"")
        replacement = key + b"=<redacted>" if key else b"Authorization: Bearer <redacted>"
        output = output.replace(value, replacement)
    return output.replace(b"\x1b", b"\\x1b").replace(b"\x07", b"\\x07")


PANEL_FIELDS = (
    b"Codex CLI:", b"Codex auth:", b"Claude Code:", b"Gemini CLI:",
    b"GitHub Copilot CLI:", b"Kiro CLI:", b"Antigravity CLI:", b"RTK:",
    b"Node.js:", b"npx:", b"codebase-memory-mcp:", b"Caveman:",
    b"Prodex home:", b"Shared CODEX_HOME:",
)


def without_panel_fields(output, excluded):
    rows = []
    skipping = False
    for line in output.splitlines():
        field = next((name for name in PANEL_FIELDS if line.startswith(name)), None)
        if field is not None:
            skipping = field in excluded
            if not skipping:
                rows.append(line)
        elif skipping and line.startswith(b" "):
            continue
        else:
            skipping = False
            rows.append(line)
    return b"\n".join(rows) + (b"\n" if output.endswith(b"\n") else b"")


def unwrapped_output(output):
    return b"".join(line.strip() for line in output.splitlines())


def run_doctor(binary, root, environment, arguments=("--install",)):
    system_tools = (Path("/bin/sh").resolve(), Path("/bin/cat").resolve())
    command = sandbox_command(
        binary,
        root,
        ["doctor", *arguments],
        environment=environment,
        extra_binaries=system_tools,
    )
    separator = command.index("--")
    for source, destination in zip(system_tools, ("/bin/sh", "/bin/cat")):
        command[separator:separator] = ["--ro-bind", str(source), destination]
        separator += 3
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
    )


class DoctorInstall01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_resolves_and_probes_only_synthetic_path_commands(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-01660-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            probe_log = root / "probes.log"
            for directory in (home, workspace, bindir):
                directory.mkdir(mode=0o700)

            # Codex auth status is a harmless fixture and must never reach a real account.
            codex = bindir / "codex"
            codex.write_text(
                "#!/bin/sh\n"
                + probe_log_script("codex", probe_log)
                + "if [ \"$1\" = login ]; then printf 'synthetic auth\\n'; exit 7; fi\n"
                + "printf 'synthetic codex 1.2.3\\n'\n"
            )
            codex.chmod(0o700)
            add_probe(
                bindir,
                "claude",
                probe_log,
                stderr="Authorization: Bearer synthetic-stderr-token\n",
            )
            explicit_claude = add_probe(root, "explicit-claude", probe_log, "synthetic explicit claude 2.3.4\n")
            add_probe(bindir, "gemini", probe_log, "\x1b[31msynthetic gemini 3.4.5\x1b[0m\n")
            add_probe(bindir, "copilot", probe_log, "synthetic copilot 4.5.6\n")
            add_probe(bindir, "kiro-cli", probe_log, "synthetic kiro 5.6.7\n")
            add_probe(bindir, "agy", probe_log, "synthetic agy 6.7.8\n")
            add_probe(bindir, "rtk", probe_log, "synthetic rtk 7.8.9\n")
            add_probe(bindir, "node", probe_log, "Authorization: Bearer synthetic-secret-token\n")
            add_probe(bindir, "npx", probe_log, "synthetic npx 9.0.1\nignored line\n")
            add_probe(bindir, "codebase-memory-mcp", probe_log)

            baseline_environment = command_environment(root, str(bindir))
            modex_environment = command_environment(root, str(bindir))
            baseline_environment["PRODEX_CLAUDE_BIN"] = str(explicit_claude)
            modex_environment["PRODEX_CLAUDE_BIN"] = str(explicit_claude)
            baseline = run_doctor(
                ORACLE, root, baseline_environment
            )
            baseline_probes = set(probe_log.read_text().splitlines())
            probe_log.unlink()
            modex = run_doctor(
                MODEX, root, modex_environment
            )
            modex_probes = set(probe_log.read_text().splitlines())

            self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
            safer_output = safer_modex_output(baseline.stdout)
            excluded_path_rows = {b"Prodex home:", b"Shared CODEX_HOME:"}
            self.assertEqual(
                without_panel_fields(safer_output, excluded_path_rows),
                without_panel_fields(modex.stdout, excluded_path_rows),
            )
            self.assertEqual(modex.stderr, baseline.stderr)
            self.assertIn(b"warn (exit exit status: 7)", modex.stdout)
            self.assertIn(b"Authorization: Bearer <redacted>", modex.stdout)
            self.assertNotIn(b"synthetic-secret-token", modex.stdout)
            self.assertNotIn(b"synthetic-stderr-token", modex.stdout)
            self.assertNotIn(b"synthetic-provider-key", modex.stdout)
            self.assertNotIn(b"synthetic-prodex-path-secret", modex.stdout)
            self.assertNotIn(b"synthetic-shared-path-secret", modex.stdout)
            self.assertIn(b"api_key=<redacted>", unwrapped_output(modex.stdout))
            self.assertIn(b"token=<redacted>", unwrapped_output(modex.stdout))
            self.assertNotIn(b"\x1b", modex.stdout)
            self.assertNotIn(b"\x07", modex.stdout)
            expected_probes = {
                "codex\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "codex\tlogin status\tpresent\tpresent\tset\tset\tset\tset",
                "explicit-claude\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "gemini\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "copilot\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "kiro-cli\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "agy\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "rtk\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "node\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "npx\t--version\tpresent\tpresent\tset\tset\tset\tset",
                "codebase-memory-mcp\t--help\tpresent\tpresent\tset\tset\tset\tset",
            }
            self.assertEqual(baseline_probes, expected_probes)
            expected_modex_probes = set()
            for line in expected_probes:
                fields = line.split("\t")
                fields[2:4] = ["absent", "absent"]
                fields[4:] = ["set" if fields[0] == "codex" else "unset"] + ["unset"] * 3
                expected_modex_probes.add("\t".join(fields))
            self.assertEqual(modex_probes, expected_modex_probes)
            self.assertFalse(Path(baseline_environment["PRODEX_HOME"]).exists())
            self.assertFalse(Path(baseline_environment["PRODEX_SHARED_CODEX_HOME"]).exists())
            self.assertFalse((home / ".codex").exists())
            self.assertEqual(list(home.iterdir()), [])

            managed_caveman = home / ".local/share/prodex-optimizers/caveman"
            managed_caveman.mkdir(parents=True)
            presence = run_doctor(
                MODEX, root, command_environment(root, "")
            )
            self.assertEqual(presence.returncode, 0)
            self.assertIn(
                b"Caveman:             degraded (managed Caveman found; integrity validation is unavailable)",
                presence.stdout,
            )

    def test_missing_commands_are_checked_and_reported_without_state_creation(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-missing-01660-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            home.mkdir(mode=0o700)
            workspace.mkdir()
            baseline = run_doctor(ORACLE, root, command_environment(root, ""))
            modex = run_doctor(MODEX, root, command_environment(root, ""))

            self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
            excluded_path_rows = {b"Prodex home:", b"Shared CODEX_HOME:"}
            self.assertEqual(
                without_panel_fields(safer_modex_output(baseline.stdout), excluded_path_rows),
                without_panel_fields(modex.stdout, excluded_path_rows),
            )
            self.assertEqual(modex.stderr, baseline.stderr)
            self.assertIn(b"Codex CLI:           missing (failed to start codex)", modex.stdout)
            self.assertIn(b"Caveman:             missing", modex.stdout)
            self.assertNotIn(b"synthetic-prodex-path-secret", modex.stdout)
            self.assertNotIn(b"synthetic-shared-path-secret", modex.stdout)
            self.assertNotIn(b"synthetic-optimizer-path-secret", modex.stdout)
            self.assertIn(b"api_key=<redacted>", unwrapped_output(modex.stdout))
            self.assertIn(b"token=<redacted>", unwrapped_output(modex.stdout))
            self.assertNotIn(b"\x1b", modex.stdout)
            self.assertNotIn(b"\x07", modex.stdout)
            self.assertFalse((home / ".prodex").exists())
            self.assertFalse((home / ".codex").exists())
            self.assertEqual(list(home.iterdir()), [])

    def test_ignored_tail_bytes_preserves_install_only_mode(self):
        cases = (
            ("attached before install", ("--tail-bytes=0", "--install")),
            ("separated after install", ("--install", "--tail-bytes", "17")),
        )
        for label, arguments in cases:
            with self.subTest(arguments=label), tempfile.TemporaryDirectory(
                prefix="modex-doctor-install-tail-bytes-01660-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                home.mkdir(mode=0o700)
                workspace.mkdir()
                environment = {
                    "HOME": str(home),
                    "PATH": "",
                    "TERM": "dumb",
                    "NO_COLOR": "1",
                    "TZ": "UTC",
                    "PRODEX_TERM_COLUMNS": "80",
                }

                baseline_plain = run_doctor(ORACLE, root, environment)
                baseline_combined = run_doctor(ORACLE, root, environment, arguments)
                modex_plain = run_doctor(MODEX, root, environment)
                modex_combined = run_doctor(MODEX, root, environment, arguments)

                self.assertEqual((baseline_plain.returncode, baseline_combined.returncode), (0, 0))
                self.assertEqual((modex_plain.returncode, modex_combined.returncode), (0, 0))
                self.assertEqual(
                    (baseline_combined.stdout, baseline_combined.stderr),
                    (baseline_plain.stdout, baseline_plain.stderr),
                )
                self.assertEqual(
                    (modex_combined.stdout, modex_combined.stderr),
                    (modex_plain.stdout, modex_plain.stderr),
                )
                self.assertEqual(
                    (modex_combined.stdout, modex_combined.stderr),
                    (baseline_combined.stdout, baseline_combined.stderr),
                )
                self.assertEqual(list(home.iterdir()), [])

    def test_duplicate_install_and_false_boolean_values_remain_invalid(self):
        cases = (
            (("--install", "--install"), b"cannot be used multiple times"),
            (("--install", "--runtime=false"), b"unexpected value 'false' for '--runtime'"),
            (("--install", "--quota=false"), b"unexpected value 'false' for '--quota'"),
            (("--runtime=false", "--install"), b"unexpected value 'false' for '--runtime'"),
            (("--tail-bytes=17", "--install=false"), b"unexpected value 'false' for '--install'"),
            (("--tail-bytes", "17", "--quota=false"), b"unexpected value 'false' for '--quota'"),
            (("--bundle=synthetic", "--install=false"), b"unexpected value 'false' for '--install'"),
            (("--install", "--help=false"), b"unexpected value 'false' for '--help'"),
            (("--install", "--tail-bytes"), b"a value is required for '--tail-bytes <BYTES>'"),
            (("--install", "--tail-bytes=-1"), b"invalid value '-1'"),
            (("--install", "--tail-bytes=12", "--tail-bytes=13"), b"cannot be used multiple times"),
        )
        for arguments, diagnostic in cases:
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory(
                prefix="modex-doctor-install-invalid-01660-"
            ) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                home.mkdir(mode=0o700)
                workspace.mkdir()
                environment = {
                    "HOME": str(home),
                    "PATH": "",
                    "TERM": "dumb",
                    "NO_COLOR": "1",
                    "TZ": "UTC",
                }
                baseline = run_doctor(ORACLE, root, environment, arguments)
                modex = run_doctor(MODEX, root, environment, arguments)
                self.assertEqual((baseline.returncode, modex.returncode), (2, 2))
                self.assertEqual((baseline.stdout, modex.stdout), (b"", b""))
                self.assertIn(diagnostic, baseline.stderr)
                self.assertIn(diagnostic, modex.stderr)
                self.assertEqual(modex.stderr, baseline.stderr)
                self.assertEqual(list(home.iterdir()), [])

    def test_skipped_codex_wrapper_is_not_executed(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-wrapper-01660-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            for directory in (home, workspace, bindir):
                directory.mkdir(mode=0o700)
            wrapper_log = root / "wrapper-runs.log"
            wrapper = bindir / "codex"
            wrapper.write_text(
                "#!/bin/sh\n"
                "# @christiandoxa/prodex synthetic wrapper fixture\n"
                f"printf '%s\\n' \"$*\" >> {shlex.quote(str(wrapper_log))}\n"
                "printf 'synthetic wrapper output\\n'\n"
            )
            wrapper.chmod(0o700)
            environment = command_environment(root, str(bindir))

            baseline = run_doctor(ORACLE, root, environment)
            self.assertEqual(baseline.returncode, 0)
            self.assertEqual(wrapper_log.read_text().splitlines(), ["--version", "login status"])
            wrapper_log.unlink()

            modex = run_doctor(MODEX, root, environment)
            self.assertEqual(modex.returncode, 0)
            self.assertIn(
                b"Codex CLI:           unavailable (PATH contains only a Prodex wrapper; it was not run)",
                modex.stdout,
            )
            self.assertIn(
                b"Codex auth:          skipped (unsafe Codex executable was not run)",
                modex.stdout,
            )
            self.assertFalse(wrapper_log.exists())
            self.assertEqual(list(home.iterdir()), [])

    def test_missing_configured_codex_path_is_redacted_before_terminal_escaping(self):
        with tempfile.TemporaryDirectory(prefix="d-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            home.mkdir(mode=0o700)
            workspace.mkdir()
            environment = command_environment(root, "")
            environment["PRODEX_CODEX_BIN"] = str(
                root / "missing-api_key=synthetic-command-path-secret\x1b[31m"
            )

            baseline = run_doctor(ORACLE, root, environment)
            modex = run_doctor(MODEX, root, environment)

            self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
            excluded_path_rows = {
                b"Codex CLI:", b"Prodex home:", b"Shared CODEX_HOME:",
            }
            self.assertEqual(
                without_panel_fields(safer_modex_output(baseline.stdout), excluded_path_rows),
                without_panel_fields(modex.stdout, excluded_path_rows),
            )
            self.assertEqual(modex.stderr, baseline.stderr)
            self.assertIn(b"Codex CLI:", modex.stdout)
            self.assertIn(b"api_key=<redacted>", unwrapped_output(modex.stdout))
            self.assertNotIn(b"synthetic-command-path-secret", modex.stdout)
            self.assertNotIn(b"\x1b", modex.stdout)
            self.assertNotIn(b"\x07", modex.stdout)
            self.assertFalse((home / ".codex").exists())

    def test_output_limit_errors_match_the_reference_missing_status(self):
        with tempfile.TemporaryDirectory(prefix="modex-doctor-install-output-cap-01660-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            for directory in (home, workspace, bindir):
                directory.mkdir(mode=0o700)
            probe_log = root / "probes.log"
            payload = root / "oversized-output"
            payload.write_bytes(b"x" * 1048577)
            node = bindir / "node"
            node.write_text(
                "#!/bin/sh\n"
                + probe_log_script("node", probe_log)
                + f"/bin/cat {shlex.quote(str(payload))}\n"
            )
            node.chmod(0o700)
            environment = command_environment(root, str(bindir))

            baseline = run_doctor(ORACLE, root, environment)
            baseline_probes = set(probe_log.read_text().splitlines())
            probe_log.unlink()
            modex = run_doctor(MODEX, root, environment)
            modex_probes = set(probe_log.read_text().splitlines())

            self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
            excluded_path_rows = {b"Prodex home:", b"Shared CODEX_HOME:"}
            self.assertEqual(
                without_panel_fields(safer_modex_output(baseline.stdout), excluded_path_rows),
                without_panel_fields(modex.stdout, excluded_path_rows),
            )
            self.assertEqual(modex.stderr, baseline.stderr)
            self.assertIn(b"Node.js:             missing (node output exceeded the limit)", modex.stdout)
            self.assertNotIn(b"synthetic-prodex-path-secret", modex.stdout)
            self.assertNotIn(b"synthetic-shared-path-secret", modex.stdout)
            self.assertNotIn(b"synthetic-optimizer-path-secret", modex.stdout)
            self.assertIn(b"api_key=<redacted>", unwrapped_output(modex.stdout))
            self.assertIn(b"token=<redacted>", unwrapped_output(modex.stdout))
            self.assertNotIn(b"\x1b", modex.stdout)
            self.assertNotIn(b"\x07", modex.stdout)
            self.assertEqual(
                baseline_probes,
                {"node\t--version\tpresent\tpresent\tset\tset\tset\tset"},
            )
            self.assertEqual(
                modex_probes,
                {"node\t--version\tabsent\tabsent\tunset\tunset\tunset\tunset"},
            )
            self.assertFalse((home / ".codex").exists())


if __name__ == "__main__":
    unittest.main()
