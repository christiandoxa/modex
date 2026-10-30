"""Characterize frozen 0.439.2 runtime WebSocket behavior on synthetic loopback data.

This is reference behavior evidence only; it does not exercise or qualify Modex.
"""

import json
import os
from pathlib import Path
import select
import time
import unittest

from test_runtime_proxy_websocket_01651_oracle import (
    RuntimeProxyWebsocketOracleFixture,
    read_websocket_frame,
    send_websocket_frame,
)


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


@unittest.skipUnless(ORACLE.is_file(), f"pinned Prodex oracle unavailable: {ORACLE}")
class RuntimeProxyWebsocket04392OracleTests(RuntimeProxyWebsocketOracleFixture):
    ORACLE = ORACLE
    ORACLE_SHA256 = ORACLE_SHA256

    def test_cross_session_interrupt_waits_then_uses_submitting_upstream(self):
        local_owner, local_other = self.open_websocket(), self.open_websocket()
        upstream_owner = upstream_other = None
        try:
            upstream_owner = self.create_response_on(local_owner, "resp_owner")
            upstream_other = self.create_response_on(local_other, "resp_other")
            foreign_interrupt = json.dumps({
                "type": "response.interrupt",
                "response_id": "resp_other",
                "mode": "discard_partial_items",
            }, separators=(",", ":"))
            send_websocket_frame(local_owner, 1, foreign_interrupt.encode(), masked=True)

            for connection in (local_owner, upstream_owner, upstream_other):
                readable, _, _ = select.select([connection], [], [], 0.5)
                self.assertFalse(readable, "0.439.2 acted before the active response completed")
            self.assertIsNone(self.process.poll(), "0.439.2 broker exited while the response was pending")

            owner_completion = b'{"type":"response.completed","response":{"id":"resp_owner","status":"completed"}}'
            send_websocket_frame(upstream_owner, 1, owner_completion, masked=False)
            local_events = []
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not any(
                opcode == 1 and b"response.completed" in payload
                for opcode, payload in local_events
            ):
                timeout = min(0.2, max(0, deadline - time.monotonic()))
                readable, _, _ = select.select([local_owner], [], [], timeout)
                if readable:
                    local_events.append(read_websocket_frame(local_owner))
            self.assertTrue(
                any(opcode == 1 and payload == owner_completion for opcode, payload in local_events),
                local_events,
            )

            readable, _, _ = select.select([upstream_owner], [], [], 2)
            self.assertTrue(readable, "0.439.2 did not forward the queued text after completion")
            opcode, payload = read_websocket_frame(upstream_owner)
            self.assertEqual((opcode, payload.decode("utf-8")), (1, foreign_interrupt))
            self.assertFalse(
                select.select([upstream_other], [], [], 0.2)[0],
                "foreign interrupt reached its response owner",
            )
            with self.assertRaises(TimeoutError):
                self.upstream.accept()
            self.assertIsNone(self.process.poll(), "0.439.2 broker exited after forwarding the text")
        finally:
            local_owner.close()
            local_other.close()
            for connection in (upstream_owner, upstream_other):
                if connection is not None:
                    connection.close()
