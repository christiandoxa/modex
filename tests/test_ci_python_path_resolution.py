"""CI wrappers must keep using the checked Python after PATH changes."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CiPythonPathResolutionTests(unittest.TestCase):
    def test_path_shadowing_cannot_replace_checked_python(self):
        with tempfile.TemporaryDirectory(prefix="modex-ci-python-path-") as temporary:
            root = Path(temporary)
            selected_bin = root / "selected-bin"
            shadow_bin = root / "shadow-bin"
            selected_bin.mkdir()
            shadow_bin.mkdir()

            selected_python = selected_bin / "python3"
            selected_python.write_text(
                "#!/bin/bash\n"
                "printf '%s\\n' \"$*\" >>\"$MODEX_SELECTED_LOG\"\n"
                "if [[ \"${1-}\" == -m && \"${2-}\" == venv ]]; then exit 47; fi\n"
                "exec \"$MODEX_REAL_PYTHON\" \"$@\"\n",
                encoding="utf-8",
            )
            selected_python.chmod(0o755)

            shadow_python = shadow_bin / "python3"
            shadow_python.write_text(
                "#!/bin/bash\n"
                "printf '%s\\n' \"$*\" >>\"$MODEX_SHADOW_LOG\"\n"
                "exec \"$MODEX_BAD_PYTHON\" \"$@\"\n",
                encoding="utf-8",
            )
            shadow_python.chmod(0o755)

            bwrap = shadow_bin / "bwrap"
            bwrap.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            bwrap.chmod(0o755)

            for entrypoint in ("run-fast.sh", "run-full.sh"):
                with self.subTest(entrypoint=entrypoint):
                    selected_log = root / f"{entrypoint}.selected.log"
                    shadow_log = root / f"{entrypoint}.shadow.log"
                    environment = {
                        "PATH": os.pathsep.join((str(selected_bin), str(shadow_bin), "/usr/bin", "/bin")),
                        "PYTHON": "python3",
                        "MODEX_REAL_PYTHON": sys.executable,
                        "MODEX_BAD_PYTHON": "/usr/bin/python3",
                        "MODEX_SELECTED_LOG": str(selected_log),
                        "MODEX_SHADOW_LOG": str(shadow_log),
                        "MODEX_TOOLCHAIN_DIR": str(root / "toolchain"),
                        "CI_EVIDENCE_DIR": str(root / f"{entrypoint}.evidence"),
                        "RUNNER_TEMP": str(root),
                        "HOME": str(root / "home"),
                        "TMPDIR": str(root / "tmp"),
                        "TMP": str(root / "tmp"),
                        "TEMP": str(root / "tmp"),
                        "LANG": "C.UTF-8",
                        "LC_ALL": "C.UTF-8",
                    }
                    result = subprocess.run(
                        ["/bin/bash", str(ROOT / "scripts/ci" / entrypoint)],
                        cwd=ROOT,
                        env=environment,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=30,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("-m venv", selected_log.read_text(encoding="utf-8"))
                    self.assertFalse(shadow_log.exists(), result.stdout)


if __name__ == "__main__":
    unittest.main()
