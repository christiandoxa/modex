"""Exercise the built artifact in an isolated filesystem with no language runtimes."""

from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CleanRuntimeTests(unittest.TestCase):
    def test_version_with_only_platform_and_official_mojo_runtime_libraries(self):
        bwrap = shutil.which("bwrap")
        if not bwrap:
            self.skipTest("bubblewrap is needed for the clean-filesystem runtime test")
        binary = ROOT / "build/modex"
        linked = subprocess.run(["ldd", str(binary)], capture_output=True, text=True,
                                timeout=10, check=True)
        libraries = set()
        allowed = {
            "libKGENCompilerRTShared.so", "libMSupportGlobals.so", "libAsyncRTRuntimeGlobals.so",
            "libc.so.6", "libm.so.6", "libstdc++.so.6", "libgcc_s.so.1",
            "ld-linux-x86-64.so.2",
        }
        for line in linked.stdout.splitlines():
            match = re.search(r"(?:=>\s+|^\s*)(/\S+)", line)
            if match:
                library = match.group(1)
                self.assertIn(Path(library).name, allowed)
                libraries.add(library)
        self.assertTrue(libraries)
        arguments = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                     "--clearenv", "--tmpfs", "/", "--proc", "/proc", "--dev", "/dev",
                     "--tmpfs", "/tmp", "--setenv", "HOME", "/tmp",
                     "--ro-bind", str(binary), "/modex"]
        for library in sorted(libraries):
            arguments.extend(["--ro-bind", library, library])
        arguments.extend(["--", "/modex", "--version"])
        result = subprocess.run(arguments, capture_output=True, timeout=10, check=False)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, b"modex 0.1.0-dev\n", b""))


if __name__ == "__main__":
    unittest.main()
