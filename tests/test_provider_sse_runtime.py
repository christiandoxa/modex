"""Run the native provider SSE driver with only its runtime dependencies."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/provider_sse_driver"


class ProviderSSERuntimeTests(unittest.TestCase):
    def test_json_runtime_fragmentation_done_and_invalid_utf8(self):
        if not DRIVER.is_file():
            self.fail(f"compile tests/provider_sse_driver.mojo first: {DRIVER}")

        with tempfile.TemporaryDirectory(prefix="modex-provider-sse-runtime-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            payload = ('data: {"message":\ndata: "café"}\n\n'
                       'data: [DONE]\n\n').encode()
            cafe = payload.index("é".encode())
            chunks = (payload[:cafe + 1], payload[cafe + 1:], b"data: \xff\n\n")
            wire = b"json 4194304 4194304 4194304\n" + b"".join(
                chunk.hex().encode() + b"\n" for chunk in chunks)
            result = subprocess.run(
                sandbox_command(DRIVER, root, []), input=wire, capture_output=True,
                timeout=15, check=False)
            self.assertEqual(
                (result.returncode, result.stdout, result.stderr),
                (0, 'VALUE\t"{\\"message\\":\\n\\"café\\"}"\nEOF\n'.encode(), b""))

            wire = b"frames 4194304 4194304 4194304\n" + b"data: \xff\n\n".hex().encode() + b"\n"
            result = subprocess.run(
                sandbox_command(DRIVER, root, []), input=wire, capture_output=True,
                timeout=15, check=False)
            self.assertEqual(
                (result.returncode, result.stdout, result.stderr),
                (0, b"ERROR\tstream did not contain valid UTF-8\n", b""))


if __name__ == "__main__":
    unittest.main()
