"""Compare doctor --install's real Codex probes without provider access."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest


MODEX = Path(os.environ.get("MODEX_BINARY", ""))
ORACLE = Path(os.environ.get("PRODEX_ORACLE_01660", ""))
CODEX = Path(os.environ.get("CODEX_BINARY", ""))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"
CODEX_SHA256 = "b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8"
PROVIDER_SECRET_KEYS = (
    "OPENAI_API_KEYS", "OPENAI_API_KEY", "ANTHROPIC_API_KEYS", "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEYS", "DEEPSEEK_API_KEY", "GEMINI_API_KEYS", "GEMINI_API_KEY",
    "GOOGLE_API_KEYS", "GOOGLE_API_KEY", "GITHUB_COPILOT_API_KEYS", "GITHUB_COPILOT_API_KEY",
)
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_isolated_environment():
    if os.environ.get("MODEX_DOCTOR_CODEX_NETNS") != "1":
        raise AssertionError("Run under unshare -Urnm with a private /tmp tmpfs")
    uid_map = Path("/proc/self/uid_map").read_text().split()
    if os.geteuid() != 0 or len(uid_map) != 3 or uid_map[0] != "0" or uid_map[2] != "1":
        raise AssertionError("Run in the rootless user namespace created by unshare -Ur")

    tmp = Path("/tmp")
    tmp_info = tmp.stat()
    if tmp_info.st_uid != os.geteuid() or stat.S_IMODE(tmp_info.st_mode) != 0o1777:
        raise AssertionError("/tmp must be user-owned with mode 1777")
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, separator, right = line.partition(" - ")
        fields = left.split()
        if separator and len(fields) >= 5 and fields[4] == "/tmp":
            mounts.append((right.split()[0], fields[6:]))
    if len(mounts) != 1 or mounts[0][0] != "tmpfs":
        raise AssertionError("/tmp must be a private tmpfs mount")
    if any(field.startswith(("shared:", "master:")) for field in mounts[0][1]):
        raise AssertionError("/tmp tmpfs must have private propagation")

    for name in ("HOME", "TMPDIR", "CODEX_HOME"):
        value = os.environ.get(name)
        if not value:
            raise AssertionError(f"{name} must be set inside the private /tmp tmpfs")
        path = Path(value).resolve(strict=True)
        info = path.stat()
        if not path.is_relative_to(tmp) or path == tmp or not path.is_dir():
            raise AssertionError(f"{name} must be a directory inside the private /tmp tmpfs")
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise AssertionError(f"{name} must be current-user-owned with mode 0700")

    for name in PROVIDER_SECRET_KEYS + PROXY_KEYS:
        if name in os.environ:
            raise AssertionError(f"{name} must be absent from the test environment")
    for path in (MODEX, ORACLE, CODEX):
        if not path.is_file() or not path.is_absolute() or path.is_relative_to(tmp):
            raise AssertionError("Build and reference binaries must be absolute paths outside /tmp")

    ip = shutil.which("ip")
    if not ip:
        raise AssertionError("iproute2 is required to verify the isolated network namespace")
    links = subprocess.run([ip, "-o", "link", "show"], check=True, text=True,
                           capture_output=True, timeout=5).stdout.splitlines()
    interfaces = []
    for line in links:
        fields = line.split(":", 2)
        flags = re.search(r"<([^>]*)>", fields[2]) if len(fields) == 3 else None
        interfaces.append((fields[1].strip().split("@", 1)[0], bool(flags and "UP" in flags[1].split(","))))
    if interfaces != [("lo", True)]:
        raise AssertionError(f"Network namespace must contain only an up loopback: {interfaces}")
    for arguments in ([ip, "route", "show", "default"], [ip, "-6", "route", "show", "default"]):
        routes = subprocess.run(arguments, check=True, text=True, capture_output=True,
                                timeout=5).stdout.strip()
        if routes:
            raise AssertionError(f"Network namespace has a default route: {routes}")


def run_codex(arguments, root):
    home = root / "home"
    codex_home = root / "codex"
    tmp = root / "tmp"
    for path in (home, codex_home, tmp):
        path.mkdir(mode=0o700)
    environment = {
        "HOME": str(home), "CODEX_HOME": str(codex_home), "TMPDIR": str(tmp),
        "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1",
    }
    return subprocess.run([str(CODEX), *arguments], cwd=root, env=environment,
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=False)


def run_doctor(binary):
    with tempfile.TemporaryDirectory(prefix="modex-doctor-codex-01660-", dir=os.environ["TMPDIR"]) as raw:
        root = Path(raw)
        home = root / "home"
        codex_home = home / ".codex"
        workspace = root / "workspace"
        bindir = root / "bin"
        tmp = root / "tmp"
        for path in (home, codex_home, workspace, bindir, tmp):
            path.mkdir(mode=0o700)
        environment = {
            "HOME": str(home), "CODEX_HOME": str(codex_home), "PATH": str(bindir),
            "TMPDIR": str(tmp), "PRODEX_HOME": str(root / "prodex"),
            "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(CODEX), "PRODEX_TERM_COLUMNS": "120",
            "OPENAI_API_KEY": "synthetic-doctor-probe-key",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TERM": "dumb", "NO_COLOR": "1",
        }
        result = subprocess.run([str(binary), "doctor", "--install"], cwd=workspace,
                                env=environment, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=30, check=False)
        forbidden = ("auth.json", "config.toml", "history.jsonl", "state.json", "profiles", "sessions")
        for state_root in (codex_home, root / "prodex", root / "shared"):
            for name in forbidden:
                if (state_root / name).exists():
                    raise AssertionError(f"doctor --install created unexpected state: {name}")
        if (home / ".prodex").exists():
            raise AssertionError("doctor --install created an application home")
        return result


def comparable_rows(output):
    return [line for line in output.splitlines()
            if not line.startswith((b"Prodex home:", b"Shared CODEX_HOME:"))]


class DoctorCodexOffline01660Tests(unittest.TestCase):
    def test_doctor_install_probes_real_codex_offline(self):
        require_isolated_environment()
        self.assertEqual(sha256_file(ORACLE), ORACLE_SHA256)
        self.assertEqual(sha256_file(CODEX), CODEX_SHA256)

        direct_results = []
        for arguments in (("--version",), ("login", "status")):
            with tempfile.TemporaryDirectory(prefix="modex-doctor-codex-", dir=os.environ["TMPDIR"]) as raw:
                direct_results.append(run_codex(arguments, Path(raw)))
        version, status = direct_results
        self.assertEqual((version.returncode, version.stdout, version.stderr),
                         (0, b"codex-cli 0.166.0\n", b""))
        self.assertEqual((status.returncode, status.stdout, status.stderr),
                         (1, b"", b"Not logged in\n"))

        outputs = []
        for binary in (ORACLE, MODEX):
            result = run_doctor(binary)
            self.assertEqual((result.returncode, result.stderr), (0, b""), result.stdout)
            self.assertIn(b"Codex CLI:           ok (codex-cli 0.166.0)", result.stdout)
            self.assertIn(b"Codex auth:          warn (exit exit status: 1)", result.stdout)
            self.assertNotIn(b"synthetic-doctor-probe-key", result.stdout + result.stderr)
            outputs.append(comparable_rows(result.stdout))
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
