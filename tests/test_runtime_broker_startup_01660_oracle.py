"""Characterize the hidden broker startup in Prodex 0.166.0 and current Modex.

This is an isolated upstream reference comparison. It records the Modex startup
gap; it does not establish broker or profile parity.
"""

import json
import socket
import stat
import subprocess
import time
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_runtime_proxy_websocket_01651_oracle import (
    RuntimeProxyWebsocketOracleFixture,
    reserve_loopback_port,
)


def write_modex_profile_fixture(root):
    home = root / "home"
    prodex_home = root / "prodex"
    logs = root / "runtime-logs"
    profile = prodex_home / "profiles" / "synthetic"
    for path in (home, prodex_home, logs, profile):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)

    (profile / "auth.json").write_text(json.dumps({
        "tokens": {
            "access_token": "synthetic-modex-profile-token",
            "account_id": "synthetic-modex-account",
        },
    }), encoding="utf-8")
    (profile / "auth.json").chmod(0o600)
    (prodex_home / "state.json").write_text(json.dumps({
        "active_profile": "synthetic",
        "profiles": {
            "synthetic": {
                "codex_home": str(profile),
                "managed": True,
                "email": "synthetic@example.test",
                "provider": {"provider_kind": "openai"},
            },
        },
        "last_run_selected_at": {},
        "response_profile_bindings": {},
        "session_profile_bindings": {},
    }), encoding="utf-8")
    (prodex_home / "state.json").chmod(0o600)

    checked_at = int(time.time())
    (prodex_home / "runtime-usage-snapshots.json").write_text(json.dumps({
        "synthetic": {
            "checked_at": checked_at,
            "plan_type": "plus",
            "five_hour_status": "Ready",
            "five_hour_remaining_percent": 100,
            "five_hour_reset_at": checked_at + 3600,
            "weekly_status": "Ready",
            "weekly_remaining_percent": 100,
            "weekly_reset_at": checked_at + 604800,
        },
    }), encoding="utf-8")
    (prodex_home / "runtime-usage-snapshots.json").chmod(0o600)
    return home, prodex_home, logs


class RuntimeBrokerStartup01660OracleTests(RuntimeProxyWebsocketOracleFixture):
    ORACLE = ORACLE
    ORACLE_SHA256 = ORACLE_SHA256

    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_file():
            raise AssertionError(
                f"Verified 0.166.0 oracle is missing: {ORACLE}; set PRODEX_ORACLE to its path"
            )
        super().setUpClass()

    def test_verified_oracle_starts_broker_while_modex_reports_missing_dispatch(self):
        self.assertIsNone(self.process.poll(), "pinned 0.166.0 broker should remain alive")
        registry_path = self.prodex_home / f"runtime-broker-{self.bootstrap['broker_key']}.json"
        capability_path = self.prodex_home / f"runtime-broker-{self.bootstrap['broker_key']}.capability"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not registry_path.is_file():
            time.sleep(0.02)
        self.assertTrue(registry_path.is_file(), "0.166.0 should publish its broker registry")
        self.assertTrue(capability_path.is_file(), "0.166.0 should publish its admin capability")
        self.assertEqual(stat.S_IMODE(capability_path.stat().st_mode), 0o600)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry["listen_addr"], f"127.0.0.1:{self.listen_port}")
        self.assertEqual(registry["current_profile"], "synthetic")
        self.assertEqual(registry["instance_id"], self.bootstrap["instance_id"])

        modex_root = self.root / "modex"
        modex_root.mkdir(mode=0o700)
        modex_home, modex_prodex_home, modex_logs = write_modex_profile_fixture(modex_root)
        modex_port = reserve_loopback_port()
        modex_bootstrap = dict(self.bootstrap)
        modex_bootstrap["listen_addr"] = f"127.0.0.1:{modex_port}"
        environment = {
            "HOME": str(modex_home),
            "PRODEX_HOME": str(modex_prodex_home),
            "PRODEX_RUNTIME_LOG_DIR": str(modex_logs),
            "PATH": "/usr/bin:/bin",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "no_proxy": "127.0.0.1,localhost,::1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        result = subprocess.run(
            [str(MODEX), "__runtime-broker"],
            input=json.dumps(modex_bootstrap).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=modex_root,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8", errors="replace"),
            "Error: this Modex development build has not implemented the requested command\n",
        )
        self.assertFalse(
            (modex_prodex_home / f"runtime-broker-{modex_bootstrap['broker_key']}.json").exists(),
            "unimplemented Modex dispatch must not publish a broker registry",
        )
        with socket.socket() as probe:
            probe.settimeout(0.2)
            with self.assertRaises(OSError):
                probe.connect(("127.0.0.1", modex_port))

        self.assertIsNone(self.process.poll(), "the oracle broker should remain available")
        with self.assertRaises(TimeoutError):
            self.upstream.accept()


if __name__ == "__main__":
    unittest.main()
