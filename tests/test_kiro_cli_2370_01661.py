"""Kiro 2.37.0 doctor discovery against Prodex 0.166.1."""

import hashlib
from pathlib import Path
import shlex
import tempfile
import unittest

from test_doctor_install_01661 import (
    MODEX,
    ORACLE,
    ORACLE_SHA256,
    add_probe,
    environment,
    run_doctor,
)


def kiro_row(output: bytes) -> bytes:
    rows = [line.strip() for line in output.splitlines() if line.strip().startswith(b"Kiro CLI:")]
    if len(rows) != 1:
        raise AssertionError(f"expected one Kiro CLI row, got {rows!r}")
    return rows[0].split(b":", 1)[1].strip()


def _run_pair(root: Path, env: dict[str, str], log: Path, expected_probe: str):
    if log.exists():
        log.unlink()
    baseline = run_doctor(ORACLE, root, env)
    if not log.is_file():
        raise AssertionError(
            f"Prodex did not probe Kiro: rc={baseline.returncode}; "
            f"stdout={baseline.stdout!r}; stderr={baseline.stderr!r}"
        )
    baseline_probe = log.read_text(encoding="utf-8").splitlines()
    log.unlink()
    modex = run_doctor(MODEX, root, env)
    modex_probe = log.read_text(encoding="utf-8").splitlines()

    if (baseline.returncode, modex.returncode) != (0, 0):
        raise AssertionError(
            f"doctor failed: Prodex={baseline.returncode} {baseline.stderr!r}; "
            f"Modex={modex.returncode} {modex.stderr!r}"
        )
    expected_row = b"ok (kiro-cli 2.37.0)"
    if kiro_row(baseline.stdout) != expected_row or kiro_row(modex.stdout) != expected_row:
        raise AssertionError(
            f"Kiro doctor row differs: Prodex={kiro_row(baseline.stdout)!r}; "
            f"Modex={kiro_row(modex.stdout)!r}"
        )
    expected = [expected_probe + "\t--version"]
    if baseline_probe != expected or modex_probe != expected:
        raise AssertionError(
            f"Kiro selection differs: Prodex={baseline_probe!r}; Modex={modex_probe!r}"
        )
    if (root / "home/.codex").exists() or list((root / "home").iterdir()):
        raise AssertionError("doctor --install changed the isolated home")


class KiroCLI2370DoctorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (
            not ORACLE.is_file()
            or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.1 release")

    def test_prefers_chat_falls_back_to_legacy_and_honors_override(self):
        with tempfile.TemporaryDirectory(prefix="modex-kiro-2370-01661-") as raw:
            root = Path(raw)
            home = root / "home"
            workspace = root / "workspace"
            bindir = root / "bin"
            home.mkdir(mode=0o700)
            workspace.mkdir(mode=0o700)
            bindir.mkdir(mode=0o700)
            log = root / "kiro-probes.log"

            def script(name: str) -> str:
                return (
                    f"printf '%s\\t%s\\n' {shlex.quote(name)} \"$*\" >> {shlex.quote(str(log))}\n"
                    "printf 'kiro-cli 2.37.0\\n'\n"
                )

            add_probe(bindir, "kiro-cli-chat", script("kiro-cli-chat"))
            add_probe(bindir, "kiro-cli", script("kiro-cli"))
            override = add_probe(root, "kiro-override", script("kiro-override"))
            env = environment(root, str(bindir))

            _run_pair(root, env, log, "kiro-cli-chat")

            (bindir / "kiro-cli-chat").unlink()
            _run_pair(root, env, log, "kiro-cli")

            env["PRODEX_KIRO_BIN"] = str(override)
            add_probe(bindir, "kiro-cli-chat", script("kiro-cli-chat"))
            _run_pair(root, env, log, "kiro-override")


if __name__ == "__main__":
    unittest.main()
