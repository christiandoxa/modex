"""Manual Linux characterization of Codex's hidden JSON alias and Super guard."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEX_BINARY = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
PRODEX_ORACLE = Path(os.environ.get("PRODEX_ORACLE", ""))
CODEX_BINARY = Path(os.environ.get("CODEX_BINARY", ""))
PRODEX_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"
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


def require_isolated_linux():
    if os.name != "posix" or not Path("/proc/self/uid_map").is_file():
        raise AssertionError("Run inside Linux unshare -Urnm with private /tmp")
    uid_map = Path("/proc/self/uid_map").read_text().split()
    if os.geteuid() != 0 or len(uid_map) != 3 or uid_map[0] != "0" or uid_map[2] != "1":
        raise AssertionError("Run in the rootless user namespace created by unshare -Ur")

    temporary_root = Path("/tmp").resolve(strict=True)
    info = temporary_root.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o1777:
        raise AssertionError("/tmp must be a user-owned tmpfs with mode 1777")
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, separator, right = line.partition(" - ")
        fields = left.split()
        if separator and len(fields) >= 5 and fields[4] == "/tmp":
            mounts.append((right.split()[0], fields[6:]))
    if len(mounts) != 1 or mounts[0][0] != "tmpfs":
        raise AssertionError("/tmp must be a private tmpfs mount")
    if any(field.startswith(("shared:", "master:")) for field in mounts[0][1]):
        raise AssertionError("/tmp tmpfs mount must have private propagation")

    for name in ("HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        value = os.environ.get(name)
        if not value:
            raise AssertionError(f"{name} must be set inside the private /tmp tmpfs")
        path = Path(value).resolve(strict=True)
        if not path.is_relative_to(temporary_root) or path == temporary_root or not path.is_dir():
            raise AssertionError(f"{name} must be a directory inside /tmp")
        path_info = path.stat()
        if path_info.st_uid != os.geteuid() or stat.S_IMODE(path_info.st_mode) != 0o700:
            raise AssertionError(f"{name} must be current-user-owned with mode 0700")

    if any(name in os.environ for name in PROVIDER_SECRET_KEYS + PROXY_KEYS):
        raise AssertionError("Provider credentials and proxy settings must be absent")
    ip = shutil.which("ip")
    if not ip:
        raise AssertionError("iproute2 is required to verify network isolation")
    links = subprocess.run([ip, "-o", "link", "show"], check=True, text=True,
                           capture_output=True, timeout=5).stdout.splitlines()
    interfaces = []
    for line in links:
        fields = line.split(":", 2)
        flags = re.search(r"<([^>]*)>", fields[2]) if len(fields) == 3 else None
        interfaces.append((fields[1].strip().split("@", 1)[0], bool(flags and "UP" in flags[1].split(","))))
    if interfaces != [("lo", True)]:
        raise AssertionError(f"network namespace must contain only an up loopback: {interfaces}")
    for arguments in ([ip, "route", "show", "default"], [ip, "-6", "route", "show", "default"]):
        routes = subprocess.run(arguments, check=True, text=True, capture_output=True,
                                timeout=5).stdout.strip()
        if routes:
            raise AssertionError(f"network namespace has a default route: {routes}")


def direct_codex_probe(arguments):
    with tempfile.TemporaryDirectory(prefix="modex-experimental-json-", dir=os.environ["TMPDIR"]) as directory:
        root = Path(directory)
        paths = {name: root / name for name in (
            "home", "codex", "tmp", "config", "cache", "data",
        )}
        for path in paths.values():
            path.mkdir(mode=0o700)
        environment = {
            "HOME": str(paths["home"]),
            "CODEX_HOME": str(paths["codex"]),
            "TMPDIR": str(paths["tmp"]),
            "XDG_CONFIG_HOME": str(paths["config"]),
            "XDG_CACHE_HOME": str(paths["cache"]),
            "XDG_DATA_HOME": str(paths["data"]),
            "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
        }
        return subprocess.run(
            [str(CODEX_BINARY), *arguments], env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=10, check=False,
        )


class SuperExperimentalJson01660Characterization(unittest.TestCase):
    def test_hidden_codex_alias_is_guarded_before_super_launch(self):
        require_isolated_linux()
        for name, path, expected in (
            ("Modex", MODEX_BINARY, None),
            ("Prodex 0.166.0", PRODEX_ORACLE, PRODEX_SHA256),
            ("Codex 0.166.0", CODEX_BINARY, CODEX_SHA256),
        ):
            self.assertTrue(path.is_file(), f"Set the {name} executable path")
            if expected:
                self.assertEqual(sha256_file(path), expected, f"{name} executable checksum mismatch")

        os.environ["MODEX_BINARY"] = str(MODEX_BINARY)
        os.environ["PRODEX_ORACLE"] = str(PRODEX_ORACLE)
        from test_super_launch import SuperLaunchTests

        help_result = direct_codex_probe(["exec", "--help"])
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn(b"--json", help_result.stdout)
        self.assertIn(b"Print events to stdout as JSONL", help_result.stdout)
        self.assertNotIn(b"--experimental-json", help_result.stdout)

        duplicate_result = direct_codex_probe(["exec", "--json", "--experimental-json"])
        self.assertEqual(duplicate_result.returncode, 2)
        self.assertIn(b"argument '--json' cannot be used multiple times", duplicate_result.stderr)

        helper = SuperLaunchTests()

        def launch(binary, flag):
            return helper.run_launch(
                binary=binary,
                scenario="exit-seven",
                temporary_directory=os.environ["TMPDIR"],
                codex_arguments=("exec", flag, "synthetic prompt"),
            )

        baseline, baseline_records, baseline_upstream, baseline_state = launch(
            PRODEX_ORACLE, "--experimental-json",
        )
        baseline_launches = [record for record in baseline_records if record.get("kind") == "launch"]
        self.assertEqual((baseline.returncode, len(baseline_launches)), (7, 1), baseline.stderr)
        self.assertEqual((baseline_upstream, baseline_state["leftovers"]), ([], []))
        self.assertEqual(baseline_launches[0]["args"][-2:], ["--experimental-json", "synthetic prompt"])

        candidate, candidate_records, candidate_upstream, candidate_state = launch(
            MODEX_BINARY, "--experimental-json",
        )
        candidate_launches = [record for record in candidate_records if record.get("kind") == "launch"]
        self.assertEqual((candidate.returncode, candidate_launches), (1, []))
        self.assertIn(b"Super startup is not implemented", candidate.stderr)
        self.assertEqual((candidate_upstream, candidate_state["leftovers"]), ([], []))

        control, control_records, control_upstream, control_state = launch(MODEX_BINARY, "--json")
        control_launches = [record for record in control_records if record.get("kind") == "launch"]
        self.assertEqual((control.returncode, len(control_launches)), (7, 1), control.stderr)
        self.assertEqual((control_upstream, control_state["leftovers"]), ([], []))
        self.assertEqual(control_launches[0]["args"][-2:], ["--json", "synthetic prompt"])

        print("Codex 0.166.0: --experimental-json is a hidden alias of JSONL --json.")
        print("Prodex 0.166.0 forwards it to the synthetic Codex client; Modex remains guarded.")
        print("The Modex --json control reaches the synthetic client; no provider requests were made.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
