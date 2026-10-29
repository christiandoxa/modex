"""Keep the active and historical CI oracle paths explicit and ordered."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class CIOracleRoutingTests(unittest.TestCase):
    def test_fast_ci_checks_04392_before_historical_oracles(self):
        script = (ROOT / "scripts/ci/run-fast.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical = script.index("reference.py oracle 0.165.1")
        cross_release = script.index("run_logged focused-python-active-cross-release")
        active_source = script.index("reference.py source active")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, historical)
        self.assertLess(active_source, active_suite)
        self.assertLess(historical, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), historical)
        self.assertLess(script.index("run_logged focused-build make build unit"), historical)
        active_tests = script[script.index("run_logged focused-python-active"):historical]
        self.assertIn("test_app_server_rpc_04392.py", active_tests)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_provider_stream_repeated_search_04392.py", script)
        self.assertIn("run_logged focused-python-active-cross-release", script)
        self.assertIn("test_session_invalid_utf8_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_ci_parity_baseline.py", script)
        self.assertIn("run_logged historical-python-01651", script)
        self.assertIn("test_provider_stream_01651_characterization.py", script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('export PRODEX_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"', script)

    def test_full_ci_checks_04392_before_historical_oracles(self):
        script = (ROOT / "scripts/ci/run-full.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical = script.index("reference.py oracle 0.165.1")
        cross_release = script.index("run_logged focused-python-active-cross-release")
        active_source = script.index("reference.py source active")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, historical)
        self.assertLess(active_source, active_suite)
        self.assertLess(historical, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), historical)
        self.assertLess(script.index("run_logged focused-build make build"), historical)
        active_tests = script[script.index("run_logged focused-python-active"):historical]
        self.assertIn("test_app_server_rpc_04392.py", active_tests)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_provider_stream_repeated_search_04392.py", script)
        self.assertIn("run_logged focused-python-active-cross-release", script)
        self.assertIn("test_session_invalid_utf8_04392.py", script[cross_release:script.index("\n", cross_release)])
        complete_suite = script.index("run_logged complete-suite make test")
        self.assertLess(historical, complete_suite)
        self.assertIn("run_logged historical-python-01651", script)
        self.assertIn("reference.py source 0.439.1", script)
        self.assertIn("reference.py source 0.165.1", script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('export PRODEX_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export MODEX_REFERENCE_04392_DIR="$MODEX_REFERENCE_DIR"', script)

    def test_historical_provider_stream_setup_does_not_require_active_oracle(self):
        import test_provider_stream_01651_characterization as historical_suite

        with tempfile.TemporaryDirectory(prefix="modex-historical-oracle-setup-") as temporary:
            root = Path(temporary)
            active_oracle = root / "oracle-01651"
            modex = root / "modex"
            missing_active = root / "missing-oracle-04392"
            active_bytes = b"synthetic historical oracle"
            active_oracle.write_bytes(active_bytes)
            modex.write_bytes(b"synthetic modex binary")
            with (
                patch.dict(os.environ, {
                    "PRODEX_ORACLE": str(missing_active),
                    "PRODEX_ORACLE_04392": str(missing_active),
                    "PRODEX_GATEWAY_ORACLE": str(missing_active),
                }),
                patch.object(historical_suite, "ORACLE_01651", active_oracle),
                patch.object(historical_suite, "ORACLE_01651_SHA256", hashlib.sha256(active_bytes).hexdigest()),
                patch.object(historical_suite, "MODEX", modex),
            ):
                historical_suite.ProviderStream01651CharacterizationTests.setUpClass()

    def run_fast_with_fake_tools(self, *, missing_active):
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

            active_oracle = temp / "oracle-04392"
            historical_oracle = temp / "oracle-01651"
            later_historical_oracle = temp / "oracle-04395"
            for path in (active_oracle, historical_oracle, later_historical_oracle):
                path.write_bytes(b"synthetic test oracle")
                path.chmod(0o755)
            events = temp / "events.log"
            fake_python = fake_bin / "python"
            fake_python.write_text(
                "#!/bin/bash\n"
                "printf 'call\\t%s\\n' \"$*\" >>\"$FAKE_LOG\"\n"
                "if [[ \"${1-}\" == -c ]]; then echo 3.14; exit 0; fi\n"
                "if [[ \"${1-}\" == --version ]]; then echo 'Python 3.14.10'; exit 0; fi\n"
                "if [[ \"${1-}\" == scripts/ci/reference.py ]]; then\n"
                "  case \"${2-}:${3-}\" in\n"
                "    oracle:active) printf 'reference\\toracle active\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_ACTIVE\" == 1 ]]; then echo 'synthetic missing Prodex 0.439.2 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_ACTIVE_ORACLE\" ;;\n"
                "    oracle:0.165.1) printf 'reference\\toracle 0.165.1\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_HISTORICAL_ORACLE\" ;;\n"
                "    oracle:0.439.5) printf '%s\\n' \"$FAKE_LATER_HISTORICAL_ORACLE\" ;;\n"
                "    source:*) printf '%s\\n' \"$FAKE_SOURCE\" ;;\n"
                "    identity:active) printf '{\"tag\":\"0.439.2\"}\\n' ;;\n"
                "    *) echo \"unexpected synthetic reference request: $*\" >&2; exit 2 ;;\n"
                "  esac\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_provider_stream_repeated_search_04392.py '* ]]; then\n"
                "  printf 'active-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${PRODEX_ORACLE_01651-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_cli_01651.py '* ]]; then\n"
                "  printf 'historical-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE_01651-}\" \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "echo 'synthetic command passed'\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            for name, body in (
                ("make", "printf 'make\\t%s\\t%s\\t%s\\n' \"$*\" \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" >>\"$FAKE_LOG\"\nexit 0\n"),
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
                "FAKE_HISTORICAL_ORACLE": str(historical_oracle),
                "FAKE_LATER_HISTORICAL_ORACLE": str(later_historical_oracle),
                "FAKE_SOURCE": str(temp / "reference-source"),
                "FAKE_LOG": str(events),
                "FAKE_MISSING_ACTIVE": "1" if missing_active else "0",
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
                str(historical_oracle),
            )

    def test_missing_active_oracle_fails_before_build_and_tests(self):
        result, events, summary, _, _ = self.run_fast_with_fake_tools(missing_active=True)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing Prodex 0.439.2 oracle", result.stdout)
        active_reference = events.index("reference\toracle active")
        self.assertFalse(any(event.startswith("make\tbuild unit\t") for event in events))
        self.assertFalse(any(event.startswith("active-test\t") for event in events))
        self.assertFalse(any(event.startswith("historical-test\t") for event in events))
        self.assertIn("reference-helper-tests: PASS", summary)
        self.assertNotIn("focused-build: PASS", summary)

    def test_active_and_historical_suites_receive_their_pinned_oracles(self):
        result, events, _, active_oracle_path, historical_oracle_path = self.run_fast_with_fake_tools(missing_active=False)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(event.startswith("active-test\t") for event in events), f"events={events!r}; output={result.stdout}")
        active = next(event for event in events if event.startswith("active-test\t"))
        historical = next(event for event in events if event.startswith("historical-test\t"))
        active_test_index = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        active_environment = active.split("\t")
        self.assertEqual(active_environment[1:4], [active_oracle_path] * 3)
        self.assertEqual(active_environment[4], historical_oracle_path)
        historical_environment = historical.split("\t")
        self.assertEqual(historical_environment[1], historical_oracle_path)
        self.assertEqual(historical_environment[2:4], ["", ""])
        self.assertEqual(historical_environment[4], active_oracle_path)
        self.assertLess(events.index("reference\toracle active"), active_test_index)
        self.assertLess(events.index("reference\toracle 0.165.1"), active_test_index)
        self.assertIn("Fast CI checks passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
