"""Run compressed rollouts through the actual session command path."""

from compression import zstd
import json
from pathlib import Path
import tempfile
import unittest

from capture_session_zstd import install_case, observe
from session_oracle import fixture
import test_cli
from test_cli import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_sessions import compare_outputs


class CompressedSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_compressed_metadata_filters_and_output(self):
        for level in (1, 3, 9, 19):
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                content = original.read_bytes() + b'{"type":"event_msg","payload":{"text":"Fixture event"}}\n' * 5000
                original.with_suffix(".jsonl.zst").write_bytes(zstd.compress(content, options={
                    zstd.CompressionParameter.compression_level: level,
                    zstd.CompressionParameter.checksum_flag: 1}))
                original.unlink()
            for arguments in (["session", "list", "--json"], ["session", "current", "--json"],
                              ["session", "list", "--id-only"],
                              ["session", "list", "--resume-command"],
                              ["session", "list", "--json", "--query", "session fixture"]):
                with self.subTest(level=level, arguments=arguments):
                    baseline, modex = compare_outputs(arguments, change)
                    self.assertEqual(modex, baseline)

    def test_lines_cross_frames_and_blocks(self):
        for mode in ("frames", "blocks"):
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                content = original.read_bytes()
                parts = [content[:10], content[10:100], content[100:]]
                if mode == "frames":
                    encoded = b"".join(zstd.compress(part) for part in parts)
                else:
                    compressor = zstd.ZstdCompressor()
                    encoded = b"".join(compressor.compress(part, zstd.ZstdCompressor.FLUSH_BLOCK) for part in parts)
                    encoded += compressor.flush()
                original.with_suffix(".jsonl.zst").write_bytes(encoded)
                original.unlink()
            with self.subTest(mode=mode):
                baseline, modex = compare_outputs(["session", "list", "--json"], change)
                self.assertEqual(modex, baseline)

    def test_malformed_release_diagnostics(self):
        capture = json.loads((ROOT / "docs/evidence/baseline/session-zstd-errors.json").read_text())
        self.assertEqual(capture["oracle_sha256"], ORACLE_SHA256)
        with tempfile.TemporaryDirectory(prefix="modex-zstd-errors-") as directory:
            for expected in capture["cases"]:
                with self.subTest(case=expected["case"]):
                    root = Path(directory) / expected["case"]
                    root.mkdir()
                    fixture(root)
                    install_case(root, expected["case"])
                    self.assertEqual(observe(MODEX, root), {key: expected[key]
                        for key in ("exit_code", "stdout", "stderr")})

    def test_noncanonical_differences_are_retained(self):
        # These preserve unapproved differences, not parity PASS results.
        capture = json.loads((ROOT / "docs/evidence/baseline/session-zstd-errors.json").read_text())
        with tempfile.TemporaryDirectory(prefix="modex-zstd-difference-") as directory:
            for record in capture["known_differences"]:
                with self.subTest(case=record["case"]):
                    root = Path(directory) / record["case"]
                    root.mkdir()
                    fixture(root)
                    install_case(root, record["case"])
                    self.assertEqual(observe(MODEX, root), record["observations"]["modex"])

    def test_decoded_line_limit(self):
        limit = 64 * 1024 * 1024
        with tempfile.TemporaryDirectory(prefix="modex-zstd-line-limit-") as directory:
            for compressed in (False, True):
                observations = []
                for name, binary in (("baseline", ORACLE), ("modex", MODEX)):
                    root = Path(directory) / f"{compressed}-{name}"
                    root.mkdir()
                    fixture(root)
                    original = next((root / "home/.codex").rglob("*.jsonl"))
                    content = b"x" * (limit + 1)
                    if compressed:
                        original.with_suffix(".jsonl.zst").write_bytes(zstd.compress(content, level=1))
                        original.unlink()
                    else:
                        original.write_bytes(content)
                    observations.append(observe(binary, root))
                with self.subTest(compressed=compressed):
                    self.assertEqual(observations[1], observations[0])
                    self.assertEqual(observations[0]["exit_code"], 1)
                    self.assertIn("exceeds safe size limit (67108864 bytes)", observations[0]["stderr"])


if __name__ == "__main__":
    unittest.main()
