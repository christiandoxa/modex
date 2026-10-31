"""Exercise real Codex with isolated local Modex fixtures and no external route."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

from test_active_baseline_01660 import ORACLE, ORACLE_SHA256


MODEX = Path(os.environ.get("MODEX_BINARY", ""))
CODEX = Path(os.environ.get("CODEX_BINARY", ""))
NODE_BIN = Path(os.environ.get("NODE_BIN", "/usr/bin"))
EXPECTED_VERSION = "0.166.0"
CODEX_SHA256 = "b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8"


def normalize_codex_capture(value):
    value = re.sub(r"modex-super-launch-[^/\" ]+", "modex-super-launch-<private>", value)
    value = re.sub(r"/\.prodex-overlay-[^/\" ]+", "/.prodex-overlay-<private>", value)
    return re.sub(r"http://127\.0\.0\.1:\d+", "http://127.0.0.1:<port>", value)


def normalize_request(value):
    if isinstance(value, dict):
        return {key: normalize_request(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_request(item) for item in value]
    return normalize_codex_capture(value) if isinstance(value, str) else value


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_isolated_environment():
    if os.environ.get("MODEX_REAL_CODEX_NETNS") != "1":
        raise AssertionError("Run under unshare -Urnm with a private /tmp tmpfs")
    uid_map = Path("/proc/self/uid_map").read_text().split()
    if os.geteuid() != 0 or len(uid_map) != 3 or uid_map[0] != "0" or uid_map[2] != "1":
        raise AssertionError("Run in the rootless user namespace created by unshare -Ur")

    tmp = Path("/tmp")
    tmp_stat = tmp.stat()
    if tmp_stat.st_uid != os.geteuid() or stat.S_IMODE(tmp_stat.st_mode) != 0o1777:
        raise AssertionError("/tmp must be user-owned with mode 1777")
    tmp_mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields, details = line.split(" - ", 1)
        fields = fields.split()
        if fields[4] == "/tmp":
            tmp_mounts.append((details.split()[0], fields[6:]))
    if len(tmp_mounts) != 1 or tmp_mounts[0][0] != "tmpfs":
        raise AssertionError("/tmp must be a private tmpfs mount")
    if any(field.startswith(("shared:", "master:")) for field in tmp_mounts[0][1]):
        raise AssertionError("/tmp tmpfs mount must have private propagation")

    for name in ("HOME", "TMPDIR"):
        value = os.environ.get(name)
        if not value:
            raise AssertionError(f"{name} must be inside the private /tmp tmpfs")
        path = Path(value).resolve(strict=True)
        if not path.is_relative_to(tmp) or path == tmp or not path.is_dir():
            raise AssertionError(f"{name} must be a directory inside the private /tmp tmpfs")
        path_stat = path.stat()
        if path_stat.st_uid != os.geteuid() or stat.S_IMODE(path_stat.st_mode) != 0o700:
            raise AssertionError(f"{name} must be current-user-owned with mode 0700")

    ip = shutil.which("ip")
    if not ip:
        raise AssertionError("iproute2 is required to verify the isolated network namespace")
    links = subprocess.run([ip, "-o", "link", "show"], check=True, text=True,
                           capture_output=True).stdout.splitlines()
    interfaces = []
    for line in links:
        fields = line.split(":", 2)
        flags = re.search(r"<([^>]*)>", fields[2]) if len(fields) == 3 else None
        interfaces.append((fields[1].strip().split("@", 1)[0], bool(flags and "UP" in flags[1].split(","))))
    if interfaces != [("lo", True)]:
        raise AssertionError(f"network namespace must contain only an already-up loopback interface: {interfaces}")
    for args in ([ip, "route", "show", "default"], [ip, "-6", "route", "show", "default"]):
        routes = subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()
        if routes:
            raise AssertionError(f"network namespace has a default route: {routes}")


class RealCodexRouteComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Set MODEX_BINARY to the candidate Modex executable")
        if not CODEX.is_file():
            raise AssertionError("Set CODEX_BINARY to the pinned Codex CLI")
        if sha256_file(CODEX) != CODEX_SHA256:
            raise AssertionError("CODEX_BINARY must identify the verified Codex 0.166.0 executable")
        if not ORACLE.is_file() or sha256_file(ORACLE) != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01660 must identify the verified Prodex 0.166.0 executable")
        cls.root = tempfile.TemporaryDirectory(prefix="modex-real-codex-auth-", dir="/tmp")
        cls.root_path = Path(cls.root.name)
        node = (NODE_BIN / "node").resolve(strict=True)
        if not node.is_file() or not os.access(node, os.X_OK):
            raise AssertionError("NODE_BIN must contain an executable node")
        cls.node_bin = cls.root_path / "node-bin"
        cls.node_bin.mkdir(mode=0o700)
        (cls.node_bin / "node").symlink_to(node)
        version_home = cls.root_path / "version-home"
        version_codex_home = version_home / ".codex"
        version_codex_home.mkdir(parents=True, mode=0o700)
        version_env = {
            "HOME": str(version_home),
            "CODEX_HOME": str(version_codex_home),
            "TMPDIR": os.environ["TMPDIR"],
            "PATH": f"{cls.node_bin}:/usr/bin:/bin",
        }
        version = subprocess.run([str(CODEX), "--version"], env=version_env,
                                 capture_output=True, text=True, timeout=10)
        version_line = re.compile(r"(?m)^codex-cli " + re.escape(EXPECTED_VERSION) + r"$")
        if version.returncode != 0 or not version_line.search(version.stdout + version.stderr):
            raise AssertionError(f"expected Codex {EXPECTED_VERSION}: {version.stdout!r} {version.stderr!r}")
        oracle = subprocess.run([str(ORACLE), "--version"], env=version_env,
                                capture_output=True, text=True, timeout=10)
        if oracle.returncode != 0 or oracle.stdout != "prodex 0.166.0\n":
            raise AssertionError(f"expected Prodex 0.166.0: {oracle.stdout!r} {oracle.stderr!r}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "root"):
            cls.root.cleanup()

    def observing_codex(self, name):
        wrapper = self.root_path / (name + "-wrapper")
        auth_capture = self.root_path / (name + "-auth.jsonl")
        exit_capture = self.root_path / (name + "-exit.jsonl")
        wrapper.write_text(
            "#!/usr/bin/python3\n"
            "import json, os, subprocess, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "home = os.environ.get('CODEX_HOME')\n"
            "auth_path = Path(home) / 'auth.json' if home else None\n"
            "if auth_path and auth_path.is_file():\n"
            "    auth = json.loads(auth_path.read_text())\n"
            "    with open(os.environ['MODEX_AUTH_CAPTURE'], 'a', encoding='utf-8') as out:\n"
            "        out.write(json.dumps({'token': auth['OPENAI_API_KEY'], 'mode': auth.get('auth_mode'), 'args': args}) + '\\n')\n"
            "if 'exec' not in args:\n"
            "    os.execv(os.environ['MODEX_REAL_CODEX'], [os.environ['MODEX_REAL_CODEX'], *args])\n"
            "before = auth_path.read_bytes()\n"
            "command = [os.environ['MODEX_REAL_CODEX'], *args]\n"
            "child = subprocess.Popen(command)\n"
            "status = child.wait()\n"
            "after = auth_path.read_bytes() if auth_path.is_file() else None\n"
            "with open(os.environ['MODEX_CODEX_EXIT_CAPTURE'], 'a', encoding='utf-8') as out:\n"
            "    out.write(json.dumps({'pid': child.pid, 'returncode': status, 'auth_unchanged': after == before}) + '\\n')\n"
            "raise SystemExit(status)\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        return wrapper, auth_capture, exit_capture

    def test_private_auth_token_authorizes_real_codex_request(self):
        from test_super_launch import SuperLaunchTests

        wrapper, token_capture, exit_capture = self.observing_codex("success")

        result, _, upstream, state = SuperLaunchTests().run_launch(
            MODEX,
            scenario="anthropic-stream",
            temporary_directory=self.root_path,
            codex_binary=wrapper,
            codex_arguments=(
                "exec", "--ephemeral", "--skip-git-repo-check", "--json", "--",
                "Reply with the synthetic provider response.",
            ),
            environment_overrides={
                "PATH": f"{self.node_bin}:/usr/bin:/bin",
                "MODEX_REAL_CODEX": str(CODEX),
                "MODEX_AUTH_CAPTURE": str(token_capture),
                "MODEX_CODEX_EXIT_CAPTURE": str(exit_capture),
                "OPENAI_API_KEY": "synthetic-wrong-openai-key",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertTrue(all(Path(path).is_relative_to(self.root_path) for path in state["leftovers"]))
        self.assertEqual(len(upstream), 1)
        self.assertEqual(upstream[0]["path"], "/anthropic/v1/messages")
        headers = {key.lower(): value for key, value in upstream[0]["headers"].items()}
        self.assertEqual(headers.get("x-api-key"), "synthetic-provider-key")
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
        exit_record = json.loads(exit_capture.read_text().splitlines()[0])
        self.assertEqual(exit_record["returncode"], 0)
        self.assertTrue(exit_record["auth_unchanged"])
        with self.assertRaises(ProcessLookupError):
            os.kill(exit_record["pid"], 0)

    def test_real_codex_surfaces_upstream_auth_failure(self):
        from test_super_launch import SuperLaunchTests

        observed = {}
        codex_args = {}
        request_bodies = {}
        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            wrapper, auth_capture, exit_capture = self.observing_codex(label)
            result, _, upstream, state = SuperLaunchTests().run_launch(
                binary,
                scenario="error-401",
                temporary_directory=self.root_path,
                codex_binary=wrapper,
                codex_arguments=(
                    "exec", "--ephemeral", "--skip-git-repo-check", "--json", "--",
                    "Reply with the synthetic provider response.",
                ),
                environment_overrides={
                    "PATH": f"{self.node_bin}:/usr/bin:/bin",
                    "MODEX_REAL_CODEX": str(CODEX),
                    "MODEX_AUTH_CAPTURE": str(auth_capture),
                    "MODEX_CODEX_EXIT_CAPTURE": str(exit_capture),
                    "OPENAI_API_KEY": "synthetic-wrong-openai-key",
                },
            )

            output = result.stdout + result.stderr
            with self.subTest(binary=label):
                self.assertEqual(result.returncode, 1, output.decode("utf-8", "replace"))
                self.assertTrue(upstream)
                for attempt in upstream:
                    self.assertEqual(attempt["path"], "/anthropic/v1/messages")
                    headers = {key.lower(): value for key, value in attempt["headers"].items()}
                    self.assertEqual(headers.get("x-api-key"), "synthetic-provider-key")
                self.assertTrue(all(Path(path).is_relative_to(self.root_path) for path in state["leftovers"]))
                self.assertNotIn(b"synthetic-provider-key", output)
                self.assertNotIn(b"synthetic-wrong-openai-key", output)
                self.assertIn(b"synthetic upstream failure", output)
                auth_records = [json.loads(line) for line in auth_capture.read_text().splitlines()]
                self.assertTrue(auth_records)
                self.assertEqual({record["mode"] for record in auth_records}, {"apikey"})
                self.assertEqual(len({record["token"] for record in auth_records}), 1)
                client_config = next(record for record in auth_records if "exec" in record["args"])
                exit_record = json.loads(exit_capture.read_text().splitlines()[0])
                self.assertEqual(exit_record["returncode"], 1)
                self.assertTrue(exit_record["auth_unchanged"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(exit_record["pid"], 0)
            overlay_entries = state["leftover_entries"]
            observed[label] = {
                "upstream_paths": sorted({attempt["path"] for attempt in upstream}),
                "exit_status": result.returncode,
                "auth_unchanged": exit_record["auth_unchanged"],
                "auth_retained": any("auth.json" in entries for entries in overlay_entries),
                "leftover_entries": overlay_entries,
            }
            codex_args[label] = normalize_codex_capture(json.dumps(client_config["args"]))
            request_bodies[label] = [json.loads(bytes.fromhex(attempt["body"])) for attempt in upstream]

        self.assertEqual(codex_args["oracle"], codex_args["modex"], observed)
        self.assertEqual(observed["oracle"]["upstream_paths"], observed["modex"]["upstream_paths"], observed)
        self.assertEqual(normalize_request(request_bodies["oracle"]), normalize_request(request_bodies["modex"]))
        print(json.dumps({
            "codex_version": EXPECTED_VERSION,
            "codex_sha256": CODEX_SHA256,
            "oracle_version": "0.166.0",
            "oracle_sha256": ORACLE_SHA256,
            "codex_args_match": True,
            "request_bodies_match": request_bodies["oracle"] == request_bodies["modex"],
            "normalized_request_bodies_match": normalize_request(request_bodies["oracle"])
            == normalize_request(request_bodies["modex"]),
            "request_counts": {key: len(value) for key, value in request_bodies.items()},
            "normalized_first_request_matches": normalize_request(request_bodies["oracle"][0])
            == normalize_request(request_bodies["modex"][0]),
            "runs": observed,
        }, indent=2))


if __name__ == "__main__":
    unittest.main()
