"""Keep the active and historical CI oracle paths explicit and ordered."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class CIOracleRoutingTests(unittest.TestCase):
    def test_anthropic_token_limit_suite_uses_both_oracle_overrides(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/oracle-01660",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
            "PRODEX_ORACLE_01651": "/synthetic/oracle-01651",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_anthropic_request_max_output_tokens_01651 as suite; print(suite.ORACLE_04392); print(suite.ORACLE_01651)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01651"])

    def test_cli_oracle_routes_split_active_and_historical_releases(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/oracle-01660",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_cli, test_active_baseline_01660 as active; print(test_cli.ORACLE); print(active.ORACLE)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01660"])

    def test_anthropic_unknown_fields_suite_uses_explicit_04392_override(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/wrong-generic-oracle",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
            "PRODEX_ORACLE_01651": "/synthetic/oracle-01651",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_anthropic_request_unknown_fields_01651_04392 as suite; print(suite.ORACLE_04392); print(suite.ORACLE_01651)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01651"])

    def test_buffered_response_shapes_suite_uses_explicit_release_overrides(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/wrong-generic-oracle",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
            "PRODEX_ORACLE_01651": "/synthetic/oracle-01651",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_provider_buffered_response_shapes_01651_04392 as suite; print(suite.ORACLE_04392); print(suite.ORACLE_01651)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01651"])

    def test_log_redaction_cross_release_suite_uses_explicit_release_overrides(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/wrong-generic-oracle",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
            "PRODEX_ORACLE_01651": "/synthetic/oracle-01651",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_log_redaction_01651_04392 as suite; print(suite.ORACLE_04392); print(suite.ORACLE_01651)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01651"])

    def test_fast_ci_keeps_active_and_historical_release_suites_ordered(self):
        script = (ROOT / "scripts/ci/run-fast.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical_04392 = script.index("reference.py oracle 0.439.2")
        historical_01651 = script.index("reference.py oracle 0.165.1")
        historical_04392_suite = script.index('run_logged historical-python-04392 "$PYTHON"')
        cross_release = script.index('run_logged historical-python-cross-release-01651-04392 "$PYTHON"')
        cross_release_tests = script[cross_release:script.index("\n", cross_release)]
        active_source = script.index("reference.py source active")
        historical_04392_source = script.index("reference.py source 0.439.2")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, active_suite)
        self.assertLess(active_source, active_suite)
        self.assertLess(active_suite, historical_04392)
        self.assertLess(active_suite, historical_04392_source)
        self.assertLess(historical_04392, historical_04392_suite)
        self.assertLess(historical_04392_source, historical_04392_suite)
        self.assertLess(historical_01651, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), active)
        self.assertLess(script.index("run_logged focused-build make build unit"), active)
        self.assertIn("test_active_baseline_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_deepseek_reasoning_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_policy_capacity_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_runtime_broker_startup_01660_oracle.py", script[active_suite:script.index("\n", active_suite)])
        historical_04392_tests = script[historical_04392_suite:script.index("\n", historical_04392_suite)]
        self.assertIn("test_cli.py", historical_04392_tests)
        self.assertIn("test_gateway_cli.py", historical_04392_tests)
        self.assertIn(
            'run_logged historical-python-cross-release-buffered-response-shapes env PRODEX_ORACLE_04392="$PRODEX_ORACLE_04392" PRODEX_ORACLE_01651="$PRODEX_ORACLE_01651" "$PYTHON" scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py',
            script,
        )
        self.assertIn("test_app_server_rpc_04392.py", historical_04392_tests)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_provider_stream_repeated_search_04392.py", script)
        self.assertIn("test_provider_stream_cross_release_characterization.py", cross_release_tests)
        self.assertIn("run_logged historical-python-cross-release-01651-04392", script)
        self.assertIn("test_anthropic_mixed_tools_01651.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_anthropic_request_max_output_tokens_01651.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_anthropic_request_unknown_fields_01651_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_cli.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_tty_fallback.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_endpoint_projection_01651_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_redaction_01651_04392.py", cross_release_tests)
        historical_suite = script.index("run_logged historical-python-01651")
        historical_tests = script[historical_suite:script.index("\n", historical_suite)]
        self.assertNotIn("test_anthropic_mixed_tools_01651.py", historical_tests)
        self.assertNotIn("test_provider_stream_cross_release_characterization.py", historical_tests)
        self.assertIn("test_session_invalid_utf8_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_resume.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_text.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_concurrency_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_profile_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_subagent_model_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_terminal_dimensions.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_ci_parity_baseline.py", script)
        self.assertIn("run_logged historical-python-01651", script)
        self.assertIn("test_provider_stream_01651_characterization.py", script)
        self.assertIn('export PRODEX_ORACLE="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('reference.py oracle 0.439.2', script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"', script)
        self.assertIn('export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-01651.txt")"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE_04392="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"', script)

    def test_full_ci_keeps_active_and_historical_release_suites_ordered(self):
        script = (ROOT / "scripts/ci/run-full.sh").read_text(encoding="utf-8")
        active = script.index("reference.py oracle active")
        historical_04392 = script.index("reference.py oracle 0.439.2")
        historical_01651 = script.index("reference.py oracle 0.165.1")
        historical_04392_suite = script.index('run_logged historical-python-04392 "$PYTHON"')
        cross_release = script.index('run_logged historical-python-cross-release-01651-04392 "$PYTHON"')
        cross_release_tests = script[cross_release:script.index("\n", cross_release)]
        active_source = script.index("reference.py source active")
        historical_04392_source = script.index("reference.py source 0.439.2")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, active_suite)
        self.assertLess(active_source, active_suite)
        self.assertLess(script.index("run_logged build-input-check"), script.index("run_logged focused-build make build"))
        self.assertLess(script.index("run_logged focused-build make build"), active_suite)
        self.assertLess(active_suite, historical_04392)
        self.assertLess(active_suite, historical_04392_source)
        self.assertLess(historical_04392, historical_04392_suite)
        self.assertLess(historical_04392_source, historical_04392_suite)
        self.assertLess(historical_01651, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), historical_01651)
        self.assertLess(script.index("run_logged focused-build make build"), historical_01651)
        self.assertIn("test_active_baseline_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_deepseek_reasoning_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_policy_capacity_01660.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_runtime_broker_startup_01660_oracle.py", script[active_suite:script.index("\n", active_suite)])
        self.assertIn("test_app_server_rpc_04392.py", script[historical_04392_suite:script.index("\n", historical_04392_suite)])
        self.assertIn(
            'run_logged historical-python-cross-release-buffered-response-shapes env PRODEX_ORACLE_04392="$PRODEX_ORACLE_04392" PRODEX_ORACLE_01651="$PRODEX_ORACLE_01651" "$PYTHON" scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py',
            script,
        )
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_provider_stream_repeated_search_04392.py", script)
        self.assertIn("test_provider_stream_cross_release_characterization.py", cross_release_tests)
        self.assertIn("run_logged historical-python-cross-release-01651-04392", script)
        self.assertIn("test_anthropic_mixed_tools_01651.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_anthropic_request_max_output_tokens_01651.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_anthropic_request_unknown_fields_01651_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_cli.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_tty_fallback.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_endpoint_projection_01651_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_log_redaction_01651_04392.py", cross_release_tests)
        historical_suite = script.index("run_logged historical-python-01651")
        historical_tests = script[historical_suite:script.index("\n", historical_suite)]
        self.assertNotIn("test_anthropic_mixed_tools_01651.py", historical_tests)
        self.assertNotIn("test_provider_stream_cross_release_characterization.py", historical_tests)
        self.assertIn("test_session_invalid_utf8_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_resume.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_text.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_concurrency_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_profile_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_subagent_model_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_terminal_dimensions.py", script[cross_release:script.index("\n", cross_release)])
        complete_suite = script.index("run_logged complete-suite make test")
        self.assertLess(historical_01651, complete_suite)
        self.assertIn("run_logged historical-python-01651", script)
        self.assertIn("reference.py source 0.439.1", script)
        self.assertIn("reference.py source 0.165.1", script)
        self.assertIn('export PRODEX_ORACLE="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('reference.py oracle 0.439.2', script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"', script)
        self.assertIn('export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-01651.txt")"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE_04392="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"', script)

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
                    "PRODEX_ORACLE_04392": "",
                    "PRODEX_GATEWAY_ORACLE": str(missing_active),
                }),
                patch.object(historical_suite, "ORACLE_01651", active_oracle),
                patch.object(historical_suite, "ORACLE_01651_SHA256", hashlib.sha256(active_bytes).hexdigest()),
                patch.object(historical_suite, "MODEX", modex),
            ):
                historical_suite.ProviderStream01651CharacterizationTests.setUpClass()

    def test_provider_stream_cross_release_uses_explicit_historical_oracle_override(self):
        import test_provider_stream_cross_release_characterization as cross_release_suite

        with tempfile.TemporaryDirectory(prefix="modex-cross-release-oracle-") as temporary:
            root = Path(temporary)
            historical_01651 = root / "oracle-01651"
            active_01660 = root / "oracle-01660"
            historical_04392 = root / "oracle-04392"
            historical_01651.write_bytes(b"synthetic historical 0.165.1 oracle")
            active_01660.write_bytes(b"synthetic active 0.166.0 oracle")
            historical_04392_bytes = b"synthetic historical 0.439.2 oracle"
            historical_04392.write_bytes(historical_04392_bytes)
            with (
                patch.dict(os.environ, {
                    "PRODEX_ORACLE": str(active_01660),
                    "PRODEX_ORACLE_01651": str(historical_01651),
                    "PRODEX_ORACLE_04392": str(historical_04392),
                }),
                patch.object(
                    cross_release_suite,
                    "ORACLE_01651_SHA256",
                    hashlib.sha256(historical_01651.read_bytes()).hexdigest(),
                ),
                patch.object(
                    cross_release_suite,
                    "ORACLE_04392_SHA256",
                    hashlib.sha256(historical_04392_bytes).hexdigest(),
                ),
            ):
                self.assertEqual(cross_release_suite.require_oracle_01651(), historical_01651)
                self.assertEqual(cross_release_suite.require_oracle_04392(), historical_04392)

            with patch.dict(os.environ, {
                "PRODEX_ORACLE": str(active_01660),
                "PRODEX_ORACLE_01651": str(historical_01651),
                "PRODEX_ORACLE_04392": "",
            }):
                with self.assertRaisesRegex(AssertionError, "PRODEX_ORACLE_04392"):
                    cross_release_suite.require_oracle_04392()

            with (
                patch.dict(os.environ, {"PRODEX_ORACLE_04392": str(historical_04392)}),
                patch.object(cross_release_suite, "ORACLE_04392_SHA256", "0" * 64),
            ):
                with self.assertRaisesRegex(AssertionError, "pinned Prodex release"):
                    cross_release_suite.require_oracle_04392()

    def test_provider_stream_cross_release_uses_pinned_cache_defaults_without_overrides(self):
        import test_provider_stream_cross_release_characterization as cross_release_suite

        with tempfile.TemporaryDirectory(prefix="modex-cross-release-oracle-cache-") as temporary:
            home = Path(temporary)
            cache = home / ".cache/modex/oracles"
            historical = cache / "0.165.1/prodex-x86_64-unknown-linux-gnu"
            historical_04392 = cache / "0.439.2/prodex-x86_64-unknown-linux-gnu"
            historical.parent.mkdir(parents=True)
            historical_04392.parent.mkdir(parents=True)
            historical_bytes = b"synthetic cached historical oracle"
            historical_04392_bytes = b"synthetic cached 0.439.2 oracle"
            historical.write_bytes(historical_bytes)
            historical_04392.write_bytes(historical_04392_bytes)
            modex = home / "modex"
            modex.write_bytes(b"synthetic modex binary")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(Path, "home", return_value=home),
                patch.object(
                    cross_release_suite,
                    "ORACLE_01651_SHA256",
                    hashlib.sha256(historical_bytes).hexdigest(),
                ),
                patch.object(
                    cross_release_suite,
                    "ORACLE_04392_SHA256",
                    hashlib.sha256(historical_04392_bytes).hexdigest(),
                ),
                patch.object(cross_release_suite, "MODEX", modex),
            ):
                self.assertEqual(cross_release_suite.require_oracle_01651(), historical)
                self.assertEqual(cross_release_suite.require_oracle_04392(), historical_04392)
                cross_release_suite.ProviderStreamCrossReleaseCharacterizationTests.setUpClass()

    def run_fast_with_fake_tools(
        self, *, missing_active, missing_04392_oracle=False, missing_04392_source=False,
    ):
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

            active_oracle = temp / "oracle-01660"
            historical_04392_oracle = temp / "oracle-04392"
            historical_oracle = temp / "oracle-01651"
            later_historical_oracle = temp / "oracle-04395"
            for path in (active_oracle, historical_04392_oracle, historical_oracle, later_historical_oracle):
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
                "    oracle:active) printf 'reference\\toracle active\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_ACTIVE\" == 1 ]]; then echo 'synthetic missing Prodex 0.166.0 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_ACTIVE_ORACLE\" ;;\n"
                "    oracle:0.439.2) printf 'reference\\toracle 0.439.2\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04392_ORACLE\" == 1 ]]; then echo 'synthetic missing historical Prodex 0.439.2 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_HISTORICAL_04392_ORACLE\" ;;\n"
                "    oracle:0.165.1) printf 'reference\\toracle 0.165.1\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_HISTORICAL_ORACLE\" ;;\n"
                "    oracle:0.439.5) printf '%s\\n' \"$FAKE_LATER_HISTORICAL_ORACLE\" ;;\n"
                "    source:active) printf 'reference\\tsource active\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_SOURCE_ACTIVE\" ;;\n"
                "    source:0.439.2) printf 'reference\\tsource 0.439.2\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04392_SOURCE\" == 1 ]]; then echo 'synthetic missing historical Prodex 0.439.2 source' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_SOURCE_04392\" ;;\n"
                "    source:*) printf '%s\\n' \"$FAKE_SOURCE_ACTIVE\" ;;\n"
                "    identity:active) printf '{\"tag\":\"0.166.0\"}\\n' ;;\n"
                "    *) echo \"unexpected synthetic reference request: $*\" >&2; exit 2 ;;\n"
                "  esac\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_active_baseline_01660.py '* ]]; then\n"
                "  printf 'active-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${PRODEX_ORACLE_01651-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_app_server_rpc_04392.py '* ]]; then\n"
                "  printf 'historical-04392-test\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE_04392-}\" \"${MODEX_REFERENCE_DIR-}\" \"${MODEX_REFERENCE_04392_DIR-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_provider_stream_repeated_search_04392.py '* ]]; then\n"
                "  printf 'cross-release-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_04392-}\" \"${PRODEX_ORACLE_01651-}\" \"${PRODEX_GATEWAY_ORACLE-}\" >>\"$FAKE_LOG\"\n"
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
                "FAKE_HISTORICAL_04392_ORACLE": str(historical_04392_oracle),
                "FAKE_HISTORICAL_ORACLE": str(historical_oracle),
                "FAKE_LATER_HISTORICAL_ORACLE": str(later_historical_oracle),
                "FAKE_SOURCE_ACTIVE": str(temp / "reference-source-01660"),
                "FAKE_SOURCE_04392": str(temp / "reference-source-04392"),
                "FAKE_LOG": str(events),
                "FAKE_MISSING_ACTIVE": "1" if missing_active else "0",
                "FAKE_MISSING_04392_ORACLE": "1" if missing_04392_oracle else "0",
                "FAKE_MISSING_04392_SOURCE": "1" if missing_04392_source else "0",
                "MODEX_CI_ARTIFACT_PRODUCER": "1",
                "PRODEX_ORACLE": "/synthetic/inherited-old-oracle",
                "PRODEX_ORACLE_04392": "/synthetic/inherited-old-historical-oracle",
                "PRODEX_GATEWAY_ORACLE": "/synthetic/inherited-old-gateway-oracle",
                "PRODEX_GATEWAY_ORACLE_04392": "/synthetic/inherited-old-historical-gateway-oracle",
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
                str(historical_04392_oracle),
                str(historical_oracle),
            )

    def test_missing_active_oracle_still_builds_but_skips_oracle_tests_and_artifacts(self):
        result, events, summary, _, _, _ = self.run_fast_with_fake_tools(missing_active=True)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing Prodex 0.166.0 oracle", result.stdout)
        active_reference = events.index("reference\toracle active")
        build_input_check = events.index("call\tscripts/ci/check-build-inputs.py")
        self.assertTrue(any(event.startswith("make\tbuild unit\t") for event in events))
        build_index = next(i for i, event in enumerate(events) if event.startswith("make\tbuild unit\t"))
        self.assertLess(build_input_check, build_index)
        self.assertLess(build_index, active_reference)
        self.assertFalse(any(event.startswith("active-test\t") for event in events))
        self.assertFalse(any(event.startswith("historical-04392-test\t") for event in events))
        self.assertFalse(any(event.startswith("historical-test\t") for event in events))
        self.assertNotIn("reference\toracle 0.439.2", events)
        self.assertIn("reference-helper-tests: PASS", summary)
        self.assertIn("build-input-check: PASS", summary)
        self.assertIn("focused-build: PASS", summary)

        workflow = (ROOT / ".github/workflows/ci-fast.yml").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("- name: Run fast CI"),
            workflow.index("- name: Package the verified Modex executable"),
        )
        package = workflow.split("- name: Package the verified Modex executable\n", 1)[1].split(
            "- name: Upload the Modex build handoff\n", 1,
        )[0]
        handoff = workflow.split("- name: Upload the Modex build handoff\n", 1)[1].split(
            "- name: Upload CI evidence\n", 1,
        )[0]
        self.assertNotIn("if:", package)
        self.assertNotIn("if:", handoff)
        consumer = workflow.split("\n  artifact-consumer:\n", 1)[1]
        self.assertTrue(consumer.startswith("    needs: linux-x86_64\n"))
        self.assertNotIn("if:", consumer)

    def test_missing_historical_04392_oracle_fails_after_active_suite(self):
        result, events, summary, _, _, _ = self.run_fast_with_fake_tools(
            missing_active=False, missing_04392_oracle=True,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing historical Prodex 0.439.2 oracle", result.stdout)
        self.assertIn("historical-04392-oracle: BLOCKED", result.stdout)
        self.assertIn("focused-python-active: PASS", summary)
        self.assertIn("reference\toracle active", events)
        self.assertIn("reference\tsource active", events)
        self.assertIn("reference\toracle 0.439.2", events)
        active_test = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        self.assertLess(active_test, events.index("reference\toracle 0.439.2"))
        self.assertFalse(any(event.startswith("historical-04392-test\t") for event in events))
        self.assertFalse(any(event.startswith("cross-release-test\t") for event in events))

    def test_missing_historical_04392_source_fails_after_active_suite(self):
        result, events, summary, _, _, _ = self.run_fast_with_fake_tools(
            missing_active=False, missing_04392_source=True,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing historical Prodex 0.439.2 source", result.stdout)
        self.assertIn("historical-04392-source: BLOCKED", result.stdout)
        self.assertIn("focused-python-active: PASS", summary)
        self.assertIn("reference\toracle active", events)
        self.assertIn("reference\tsource active", events)
        self.assertIn("reference\toracle 0.439.2", events)
        self.assertIn("reference\tsource 0.439.2", events)
        active_test = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        self.assertLess(active_test, events.index("reference\toracle 0.439.2"))
        self.assertLess(active_test, events.index("reference\tsource 0.439.2"))
        self.assertFalse(any(event.startswith("historical-04392-test\t") for event in events))

    def test_active_and_historical_suites_receive_their_pinned_oracles(self):
        (result, events, _, active_oracle_path, historical_04392_oracle_path,
         historical_01651_oracle_path) = self.run_fast_with_fake_tools(missing_active=False)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(event.startswith("active-test\t") for event in events), f"events={events!r}; output={result.stdout}")
        active = next(event for event in events if event.startswith("active-test\t"))
        historical_04392 = next(event for event in events if event.startswith("historical-04392-test\t"))
        cross_release = next(event for event in events if event.startswith("cross-release-test\t"))
        historical_01651 = next(event for event in events if event.startswith("historical-test\t"))
        active_test_index = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        active_environment = active.split("\t")
        self.assertEqual(active_environment[1], active_oracle_path)
        self.assertEqual(active_environment[2], "")
        self.assertEqual(active_environment[3], active_oracle_path)
        self.assertEqual(active_environment[4], "")
        historical_04392_environment = historical_04392.split("\t")
        self.assertEqual(historical_04392_environment[1:5], [
            active_oracle_path,
            historical_04392_oracle_path,
            active_oracle_path,
            historical_04392_oracle_path,
        ])
        self.assertTrue(historical_04392_environment[5].endswith("reference-source-01660"))
        self.assertTrue(historical_04392_environment[6].endswith("reference-source-04392"))
        cross_release_environment = cross_release.split("\t")
        self.assertEqual(cross_release_environment[1:5], [
            active_oracle_path,
            historical_04392_oracle_path,
            historical_01651_oracle_path,
            active_oracle_path,
        ])
        historical_01651_environment = historical_01651.split("\t")
        self.assertEqual(historical_01651_environment[1], historical_01651_oracle_path)
        self.assertEqual(historical_01651_environment[2:4], ["", ""])
        self.assertEqual(historical_01651_environment[4], historical_04392_oracle_path)
        self.assertLess(events.index("reference\toracle active"), active_test_index)
        self.assertLess(events.index("reference\tsource active"), active_test_index)
        self.assertLess(active_test_index, events.index("reference\toracle 0.439.2"))
        historical_04392_test_index = events.index(next(
            event for event in events if event.startswith("historical-04392-test\t")
        ))
        self.assertLess(events.index("reference\toracle 0.439.2"), historical_04392_test_index)
        self.assertLess(events.index("reference\toracle 0.165.1"), events.index(cross_release))
        self.assertIn("Fast CI checks passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
