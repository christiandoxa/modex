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


if __name__ == "__main__":
    unittest.main()
