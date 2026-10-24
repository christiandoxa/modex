"""Interoperability regressions for the native provider SSE framer and assembler.

Cases are derived from the frozen source contract documented in
fixtures/provider-sse/README.md; they are not observations from the Prodex binary.
"""

import json
import os
import random
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get("PROVIDER_SSE_DRIVER", ROOT / "build/tests/provider_sse_driver"))


def run(mode, payload, limits=(4194304, 4194304, 4194304), chunks=None):
    if chunks is None:
        chunks = [payload]
    header = f"{mode} {limits[0]} {limits[1]} {limits[2]}\n"
    wire = header + "".join(chunk.hex() + "\n" for chunk in chunks)
    proc = subprocess.run([str(DRIVER)], input=wire.encode(), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15, check=False)
    if proc.returncode:
        raise AssertionError(f"driver exited {proc.returncode}: {proc.stderr.decode(errors='replace')}")
    if proc.stderr:
        raise AssertionError(f"driver wrote to stderr: {proc.stderr.decode(errors='replace')}")
    records = []
    for row in proc.stdout.decode().splitlines():
        if row == "EOF":
            records.append(("EOF", None))
        elif row.startswith("ERROR\t"):
            records.append(("ERROR", row.split("\t", 1)[1]))
        else:
            kind, value = row.split("\t", 1)
            records.append((kind, json.loads(value)))
    if not records or records[-1][0] not in ("EOF", "ERROR"):
        raise AssertionError(f"driver omitted EOF or ERROR: {records!r}")
    if any(kind == "EOF" for kind, _ in records[:-1]):
        raise AssertionError(f"driver wrote records after EOF: {records!r}")
    return proc.returncode, records


def record_values(kind, *values):
    return [(kind, value) for value in values] + [("EOF", None)]


class ProviderSSETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.is_file():
            raise AssertionError(f"compile tests/provider_sse_driver.mojo first: {DRIVER}")

    def test_wire_delimiters_data_field_and_ignored_fields(self):
        payload = (b"event: x\r\ndata:one\n data: ignored\ndata:  two\r\n"
                   b"id: 4\n\n\ndata: tail\r")
        self.assertEqual(run("frames", payload)[1], record_values("FRAME", "one", " two", "tail"))

    def test_lone_cr_is_not_a_delimiter_and_trailing_cr_is_trimmed(self):
        self.assertEqual(run("frames", b"data: a\rdata: b\n\n")[1], record_values("FRAME", "a\rdata: b"))

    def test_bom_is_preserved_and_invalid_utf8_fails(self):
        self.assertEqual(run("frames", b"\xef\xbb\xbfdata: x\n\n")[1], [("EOF", None)])
        self.assertEqual(run("frames", b"data: \xff\n\n")[1], [("ERROR", "stream did not contain valid UTF-8")])

    def test_empty_frames_and_eof_partial_line(self):
        self.assertEqual(run("frames", b"\n\ndata: eof")[1], record_values("FRAME", "eof"))

    def test_eof_carriage_return_preserves_completed_frame(self):
        for ending in (b"\r", b"\r\r"):
            payload = b"data: value\n" + ending
            self.assertEqual(run("frames", payload)[1], record_values("FRAME", "value"))
        self.assertEqual(run("json", b'data: {"x":1}\n\r')[1],
                         record_values("VALUE", '{"x":1}'))

    def test_every_byte_cut_matches_single_chunk(self):
        payload = "data: héllo\r\nignored: y\ndata: z\n\n".encode()
        expected = run("frames", payload)[1]
        for cut in range(len(payload) + 1):
            self.assertEqual(run("frames", payload, chunks=[payload[:cut], payload[cut:]])[1], expected, cut)

    def test_seeded_chunk_schedules_match_single_chunk(self):
        payload = b"data: {\"x\": [1,2]}\n\ndata: {\"y\":true}\n\n"
        expected = run("json", payload)[1]
        rng = random.Random(0x535345)
        for _ in range(24):
            cuts = sorted(rng.sample(range(1, len(payload)), 5))
            points = [0, *cuts, len(payload)]
            chunks = [payload[a:b] for a, b in zip(points, points[1:])]
            self.assertEqual(run("json", payload, chunks=chunks)[1], expected)

    def test_line_limit_exact_and_one_over(self):
        exact = b"data: x\n\n"
        self.assertEqual(run("frames", exact, (8, 64, 64))[1], record_values("FRAME", "x"))
        self.assertEqual(run("frames", b"data: xx\n\n", (8, 64, 64))[1], [("ERROR", "provider SSE line exceeded safe size limit (8)")])

    def test_event_limit_includes_separator_bytes(self):
        self.assertEqual(run("frames", b"data: a\ndata: b\n\n", (64, 4, 64))[1], record_values("FRAME", "a", "b"))
        self.assertEqual(run("frames", b"data: a\ndata: bc\n\n", (64, 4, 64))[1], [("ERROR", "provider SSE event exceeded safe size limit (4)")])

    def test_invalid_utf8_precedes_line_size_error(self):
        self.assertEqual(run("frames", b"\xff123456789\n", (4, 64, 64))[1], [("ERROR", "stream did not contain valid UTF-8")])

    def test_joined_then_separate_json_values(self):
        payload = b'data: {"a":\ndata: 1}\n\ndata: {"n":2}\ndata: {"n":3}\n\n'
        self.assertEqual(run("json", payload, (128, 128, 3))[1],
                         record_values("VALUE", '{"a":\n1}', '{"n":2}', '{"n":3}'))

    def test_accumulation_joins_without_newline_and_flushes_on_done(self):
        payload = b"data: {\"a\":\n\ndata: 1}\n\ndata: [DONE]\ndata: ignored\n\n"
        self.assertEqual(run("json", payload)[1], record_values("VALUE", '{"a":1}'))

    def test_done_any_data_line_flushes_and_repeated_done_is_idempotent(self):
        payload = b"data: {\"x\":1}\n\ndata: [DONE]\ndata: {\"ignored\":2}\n\ndata: [DONE]\n\n"
        self.assertEqual(run("json", payload)[1], record_values("VALUE", '{"x":1}'))

    def test_done_stops_before_malformed_or_oversized_trailing_input(self):
        prefix = b'data: {"x":1}\n\ndata: [DONE]\n\n'
        for trailing in (b"data: \xff\n\n", b"x" * 65 + b"\n"):
            self.assertEqual(run("json", prefix + trailing, (64, 64, 64))[1],
                             record_values("VALUE", '{"x":1}'))

    def test_exact_and_exceeded_accumulation_limit(self):
        exact = b"data: {\n\ndata: \"x\":1}\n\n"
        self.assertEqual(run("json", exact, (64, 64, 8))[1], record_values("VALUE", '{"x":1}'))
        over = b"data: {\n\ndata: \"x\":123}\n\n"
        self.assertEqual(run("json", over, (64, 64, 8))[1], [("ERROR", "provider SSE accumulated JSON exceeded safe size limit (8)")])

    def test_nul_and_bom_are_not_silently_normalized(self):
        self.assertEqual(run("json", b"data: \x00\n\n")[1][0][0], "ERROR")
        self.assertEqual(run("json", b"data: \xef\xbb\xbf{}\n\n")[1][0][0], "ERROR")

    def test_default_cap_accepts_four_mib_line_and_rejects_one_byte_over(self):
        exact = b"data: " + b"a" * (4 * 1024 * 1024 - len(b"data: \n")) + b"\n\n"
        self.assertEqual(run("frames", exact)[1][0], ("FRAME", "a" * (4 * 1024 * 1024 - len(b"data: \n"))))
        over = b"x" * (4 * 1024 * 1024 + 1) + b"\n"
        self.assertEqual(run("frames", over)[1], [("ERROR", "provider SSE line exceeded safe size limit (4194304)")])

    def test_completed_frames_survive_a_later_parse_error(self):
        payload = b"data: first\n\ndata: \xff\n\n"
        self.assertEqual(run("frames", payload)[1],
                         [("FRAME", "first"), ("ERROR", "stream did not contain valid UTF-8")])


if __name__ == "__main__":
    unittest.main()
