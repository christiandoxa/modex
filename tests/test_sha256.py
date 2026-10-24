"""Independent SHA-256 checks against the Python standard library."""

import hashlib
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from test_cli import ROOT
from session_oracle import sandbox_command


DRIVER = Path(os.environ.get("SHA256_DRIVER", ROOT / "build/tests/sha256_driver"))


def digest_chunks(chunks):
    encoded = b"".join(chunk.hex().encode("ascii") + b"\n" for chunk in chunks)
    return subprocess.run([str(DRIVER), "stdin"], input=encoded, capture_output=True,
                          timeout=30, check=False)


class SHA256Tests(unittest.TestCase):
    def test_file_hash_without_external_implementation_helpers(self):
        with tempfile.TemporaryDirectory(prefix="modex-sha256-runtime-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            data = bytes(range(256)) * 257
            path = root / "fixture.bin"
            path.write_bytes(data)
            result = subprocess.run(
                sandbox_command(DRIVER, root, ["file", str(path), str(len(data))]),
                capture_output=True, timeout=30, check=False,
            )
            self.assertEqual((result.returncode, result.stdout.strip(), result.stderr),
                             (0, hashlib.sha256(data).hexdigest().encode(), b""))

    def test_seeded_payloads_at_block_and_padding_boundaries(self):
        source = random.Random(741_203)
        sizes = (0, 1, 55, 56, 63, 64, 65, 111, 112, 119, 120, 127, 128, 129,
                 191, 192, 193, 255, 256, 257, 4097)
        for size in sizes:
            with self.subTest(size=size):
                data = source.randbytes(size)
                chunks = []
                offset = 0
                while offset < len(data):
                    count = source.randint(1, 137)
                    chunks.append(data[offset:offset + count])
                    offset += count
                if not chunks:
                    chunks = [b""]
                result = digest_chunks(chunks)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(result.stdout.decode().strip(), hashlib.sha256(data).hexdigest())

    def test_large_incremental_binary_payload(self):
        source = random.Random(92_041)
        data = source.randbytes(1_250_003)
        result = digest_chunks(data[index:index + 8191] for index in range(0, len(data), 8191))
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(result.stdout.decode().strip(), hashlib.sha256(data).hexdigest())

    def test_file_hashing_limits_and_empty_file(self):
        data = (bytes(range(256)) * 512) + b"sha256 file fixture"
        with tempfile.TemporaryDirectory(prefix="modex-sha256-") as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(data)
            expected = hashlib.sha256(data).hexdigest().encode()
            exact = subprocess.run([str(DRIVER), "file", str(path), str(len(data))],
                                   capture_output=True, timeout=30, check=False)
            self.assertEqual((exact.returncode, exact.stdout.strip(), exact.stderr),
                             (0, expected, b""))
            for limit in (len(data) - 1, -1):
                with self.subTest(limit=limit):
                    rejected = subprocess.run([str(DRIVER), "file", str(path), str(limit)],
                                              capture_output=True, timeout=30, check=False)
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn(b"size limit", rejected.stderr)
            empty = Path(directory) / "empty.bin"
            empty.write_bytes(b"")
            empty_result = subprocess.run([str(DRIVER), "file", str(empty), "0"],
                                          capture_output=True, timeout=30, check=False)
            self.assertEqual((empty_result.returncode, empty_result.stdout.strip(),
                              empty_result.stderr),
                             (0, hashlib.sha256(b"").hexdigest().encode(), b""))
            missing = Path(directory) / "missing.bin"
            missing_result = subprocess.run([str(DRIVER), "file", str(missing), "10"],
                                            capture_output=True, timeout=30, check=False)
            self.assertNotEqual(missing_result.returncode, 0)
            self.assertNotEqual(missing_result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
