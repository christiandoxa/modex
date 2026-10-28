"""Keep the active and historical CI oracle paths explicit and ordered."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CIOracleRoutingTests(unittest.TestCase):
    def test_fast_ci_builds_and_checks_active_baseline_before_required_history(self):
        script = (ROOT / "scripts/ci/run-fast.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical = script.index("reference.py oracle 0.439.2")

        self.assertLess(active, historical)
        self.assertLess(script.index("run_logged build-input-check"), historical)
        self.assertLess(script.index("run_logged focused-build make build unit"), historical)
        self.assertLess(script.index("run_logged focused-python-01651"), historical)
        active_tests = script[script.index("run_logged focused-python-01651"):historical]
        self.assertIn("test_super_model_toml_01651.py", active_tests)
        self.assertIn("test_super_launch_01651.py", active_tests)
        self.assertIn("test_ci_parity_baseline.py", script)
        self.assertIn("test_cli_01651.py test_gateway_cli_01651.py test_provider_stream_01651_characterization.py test_session_query_01651.py", script)
        self.assertIn("test_session_query_01651.py test_unicode_case_properties.py", script)
        self.assertIn('export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"', script)
        self.assertIn('export PRODEX_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertNotIn('export PRODEX_ORACLE_04392="$PRODEX_ORACLE"', script)

    def test_full_ci_preserves_active_evidence_before_required_history(self):
        script = (ROOT / "scripts/ci/run-full.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical = script.index("reference.py oracle 0.439.2")

        self.assertLess(active, historical)
        self.assertLess(script.index("run_logged build-input-check"), historical)
        self.assertLess(script.index("run_logged focused-build make build"), historical)
        self.assertLess(script.index("run_logged focused-python-01651"), historical)
        active_tests = script[script.index("run_logged focused-python-01651"):historical]
        self.assertIn("test_super_model_toml_01651.py", active_tests)
        self.assertIn("test_super_launch_01651.py", active_tests)
        self.assertIn("test_cli_01651.py test_gateway_cli_01651.py test_provider_stream_01651_characterization.py test_session_query_01651.py", script)
        self.assertNotIn("test_unicode_case_properties.py", script)
        self.assertIn("reference.py source 0.439.2", script)
        self.assertIn('export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"', script)
        self.assertIn('export PRODEX_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"', script)
        self.assertNotIn('export PRODEX_ORACLE_04392="$PRODEX_ORACLE"', script)

    def run_fast_with_fake_tools(self, *, missing_04392):
        with tempfile.TemporaryDirectory(prefix="modex-ci-oracle-routing-") as temporary:
            temp = Path(temporary)
            root = temp / "repo"
            ci = root / "scripts/ci"
            ci.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/ci/run-fast.sh", ci / "run-fast.sh")
            shutil.copy2(ROOT / "scripts/ci/private-scratch.sh", ci / "private-scratch.sh")
            for name in ("bootstrap.sh", "validate-workflows.sh"):
                path = ci / name
                path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            fake_bin = temp / "fake-bin"
            fake_bin.mkdir()
            fake_bwrap = temp / "fake-tools/bwrap"
            fake_bwrap.parent.mkdir()
            fake_bwrap.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_bwrap.chmod(0o755)
            ensure_bwrap = ci / "ensure-bwrap.sh"
            ensure_bwrap.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$FAKE_BWRAP\"\n", encoding="utf-8"
            )
            ensure_bwrap.chmod(0o755)

            active_oracle = temp / "oracle-01651"
            legacy_oracle = temp / "oracle-04392"
            for path in (active_oracle, legacy_oracle):
                path.write_bytes(b"synthetic test oracle")
            active_oracle.chmod(0o755)
            legacy_oracle.chmod(0o755)
            events = temp / "events.log"
            fake_python = fake_bin / "python"
            fake_python.write_text(
                "#!/bin/bash\n"
                "printf 'call\\t%s\\n' \"$*\" >>\"$FAKE_LOG\"\n"
                "if [[ \"${1-}\" == -c ]]; then echo 3.14; exit 0; fi\n"
                "if [[ \"${1-}\" == --version ]]; then echo 'Python 3.14.10'; exit 0; fi\n"
                "if [[ \"${1-}\" == scripts/ci/reference.py ]]; then\n"
                "  case \"${2-}:${3-}\" in\n"
                "    oracle:active) printf 'reference\\toracle active\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_ACTIVE_ORACLE\" ;;\n"
                "    oracle:0.439.2) printf 'reference\\toracle 0.439.2\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04392\" == 1 ]]; then echo 'synthetic missing Prodex 0.439.2 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_LEGACY_ORACLE\" ;;\n"
                "    oracle:0.439.5) printf '%s\\n' \"$FAKE_LEGACY_ORACLE\" ;;\n"
                "    source:*) printf '%s\\n' \"$FAKE_SOURCE\" ;;\n"
                "    identity:active) printf '{\"tag\":\"0.165.1\"}\\n' ;;\n"
                "    *) echo \"unexpected synthetic reference request: $*\" >&2; exit 2 ;;\n"
                "  esac\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_cli_01651.py '* ]]; then\n"
                "  printf 'active-test\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE_01651-}\" \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_cli.py '* ]]; then\n"
                "  printf 'legacy-test\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" \"${PRODEX_GATEWAY_ORACLE-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "echo 'synthetic command passed'\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            for name, body in (
                ("make", "printf 'make\\t%s\\t%s\\t%s\\t%s\\n' \"$*\" \"${PRODEX_ORACLE_01651-}\" \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" >>\"$FAKE_LOG\"\nexit 0\n"),
                ("git", "if [[ \"${1-}\" == rev-parse && \"${2-}\" == HEAD ]]; then printf '%040d\\n' 0; else exit 2; fi\n"),
            ):
                path = fake_bin / name
                path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
                path.chmod(0o755)

            toolchain_bin = temp / "toolchain/bin"
            toolchain_bin.mkdir(parents=True)
            mojo = toolchain_bin / "mojo"
            mojo.write_text("#!/bin/sh\necho 'Mojo 1.2.0 (2016d0cd)'\n", encoding="utf-8")
            mojo.chmod(0o755)
            environment = {
                "PATH": os.pathsep.join((str(fake_bin), "/usr/bin", "/bin")),
                "PYTHON": str(fake_python),
                "MODEX_TOOLCHAIN_DIR": str(toolchain_bin.parent),
                "MODEX_REFERENCE_CACHE": str(temp / "cache"),
                "CI_EVIDENCE_DIR": str(temp / "evidence"),
                "RUNNER_TEMP": str(temp / "runner"),
                "HOME": str(temp / "home"),
                "TMPDIR": str(temp / "tmp"),
                "FAKE_BWRAP": str(fake_bwrap),
                "FAKE_ACTIVE_ORACLE": str(active_oracle),
                "FAKE_LEGACY_ORACLE": str(legacy_oracle),
                "FAKE_SOURCE": str(temp / "reference-source"),
                "FAKE_LOG": str(events),
                "FAKE_MISSING_04392": "1" if missing_04392 else "0",
                "MODEX_CI_ARTIFACT_PRODUCER": "1",
                "PRODEX_ORACLE": "/synthetic/inherited-old-oracle",
                "PRODEX_GATEWAY_ORACLE": "/synthetic/inherited-old-gateway-oracle",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            result = subprocess.run(
                ["/bin/bash", str(ci / "run-fast.sh")],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
                check=False,
            )
            summary_path = temp / "evidence/summary.txt"
            summary = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
            return (
                result,
                events.read_text(encoding="utf-8").splitlines(),
                summary,
                str(active_oracle),
                str(legacy_oracle),
            )

    def test_missing_historical_oracle_fails_after_active_build_and_test(self):
        result, events, summary, active_oracle_path, _ = self.run_fast_with_fake_tools(missing_04392=True)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing Prodex 0.439.2 oracle", result.stdout)
        active_reference = events.index("reference\toracle active")
        build = next(i for i, event in enumerate(events) if event.startswith("make\tbuild unit\t"))
        active_test = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        missing_oracle = events.index("reference\toracle 0.439.2")

        self.assertLess(active_reference, build)
        self.assertLess(build, active_test)
        self.assertLess(active_test, missing_oracle)
        self.assertFalse(any(event.startswith("legacy-test\t") for event in events))
        active_environment = events[active_test].split("\t")
        self.assertEqual(active_environment[1], active_oracle_path)
        self.assertEqual(active_environment[2:], ["", ""])
        self.assertIn("focused-build: PASS", summary)
        self.assertIn("focused-python-01651: PASS", summary)

    def test_legacy_suite_receives_only_the_explicit_04392_oracle(self):
        result, events, _, active_oracle_path, legacy_oracle_path = self.run_fast_with_fake_tools(missing_04392=False)

        self.assertEqual(result.returncode, 0, result.stdout)
        active = next(event for event in events if event.startswith("active-test\t"))
        legacy = next(event for event in events if event.startswith("legacy-test\t"))
        active_environment = active.split("\t")
        legacy_environment = legacy.split("\t")
        self.assertEqual(active_environment[1], active_oracle_path)
        self.assertEqual(active_environment[2:], ["", ""])
        self.assertEqual(legacy_environment[1], legacy_oracle_path)
        self.assertEqual(legacy_environment[1], legacy_environment[2])
        self.assertEqual(legacy_environment[2], legacy_environment[3])
        self.assertIn("Fast CI checks passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
