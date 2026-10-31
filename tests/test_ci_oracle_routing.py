"""Keep the active and historical CI oracle paths explicit and ordered."""

import ast
import collections
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def unittest_files(script):
    return [
        name
        for line in script.splitlines()
        if "scripts/ci/run-unittest.py" in line
        for name in re.findall(r"test_[A-Za-z0-9_]+\.py", line)
    ]


def unittest_files_for_lane(script, lane):
    lines = [line.lstrip() for line in script.splitlines() if line.lstrip().startswith(f"run_logged {lane} ")]
    if len(lines) != 1:
        raise AssertionError(f"expected one {lane} command, found {len(lines)}")
    return set(re.findall(r"test_[A-Za-z0-9_]+\.py", lines[0]))


def test_uses_04392_cli_fixture(test_name):
    tree = ast.parse((ROOT / "tests" / test_name).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "test_cli":
            if any(alias.name in {"ORACLE", "ORACLE_SHA256"} for alias in node.names):
                return True
        if isinstance(node, ast.Attribute) and node.attr == "setUpClass":
            fixture_class = node.value
            if isinstance(fixture_class, ast.Attribute) and fixture_class.attr == "CliTests":
                return True
        if isinstance(node, ast.Name) and node.id in {"ORACLE_04392", "ORACLE_04392_SHA256"}:
            return True
        if isinstance(node, ast.Attribute) and node.attr in {"ORACLE", "ORACLE_SHA256"}:
            if isinstance(node.value, ast.Name) and node.value.id == "test_cli":
                return True
    return False


class CIOracleRoutingTests(unittest.TestCase):
    def test_provider_framing_suite_uses_active_oracle_and_active_ci_lane(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/active-oracle-01662",
            "PRODEX_ORACLE_01660": "/synthetic/historical-oracle-01660",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_provider_framing_01662 as suite; print(suite.ORACLE)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/active-oracle-01662"])

        for script_path in (ROOT / "scripts/ci/run-fast.sh", ROOT / "scripts/ci/run-full.sh"):
            with self.subTest(script=script_path.name):
                script = script_path.read_text(encoding="utf-8")
                active_tests = unittest_files_for_lane(script, "focused-python-active")
                self.assertIn("test_provider_framing_01662.py", active_tests)
                self.assertIn("test_provider_relay_01662.py", active_tests)
                for line in script.splitlines():
                    if line.lstrip().startswith("run_logged historical-") and "scripts/ci/run-unittest.py" in line:
                        self.assertNotIn("test_provider_framing_01662.py", line)

    def test_anthropic_token_limit_suite_uses_both_oracle_overrides(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/oracle-01662",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
            "PRODEX_ORACLE_01651": "/synthetic/oracle-01651",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import test_anthropic_request_max_output_tokens_01651 as suite; print(suite.ORACLE_04392); print(suite.ORACLE_01651)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["/synthetic/oracle-04392", "/synthetic/oracle-01651"])

    def test_cli_and_01661_and_01660_fixtures_use_explicit_release_environments(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/oracle-01662",
            "PRODEX_ORACLE_01661": "/synthetic/oracle-01661",
            "PRODEX_ORACLE_01660": "/synthetic/oracle-01660",
            "PRODEX_ORACLE_04392": "/synthetic/oracle-04392",
        }
        program = "import test_cli, test_active_baseline_01661 as previous, test_active_baseline_01660 as active, test_super_launch_01660 as super_launch, test_login_help_01660 as login_help, test_inspection_cli_01660 as inspection, test_root_help_errors_01660 as root_help; print(test_cli.ORACLE); print(previous.ORACLE); print(active.ORACLE); print(super_launch.ORACLE); print(login_help.ORACLE); print(inspection.ORACLE); print(root_help.ORACLE)"
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.splitlines(), [
            "/synthetic/oracle-04392",
            "/synthetic/oracle-01661",
            "/synthetic/oracle-01660",
            "/synthetic/oracle-01660",
            "/synthetic/oracle-01660",
            "/synthetic/oracle-01660",
            "/synthetic/oracle-01660",
        ])

        with tempfile.TemporaryDirectory(prefix="modex-01660-oracle-cache-") as temporary:
            cache_environment = dict(environment)
            cache_environment.pop("PRODEX_ORACLE_01661")
            cache_environment.pop("PRODEX_ORACLE_01660")
            cache_environment["MODEX_REFERENCE_CACHE"] = temporary
            cached = subprocess.run(
                [sys.executable, "-c", program],
                cwd=ROOT, env=cache_environment, capture_output=True, text=True, check=True,
            )
            expected_01661 = str(Path(temporary) / "oracles/0.166.1/prodex-x86_64-unknown-linux-gnu")
            expected = str(Path(temporary) / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu")
            self.assertEqual(cached.stdout.splitlines(), [
                "/synthetic/oracle-04392",
                expected_01661,
                expected,
                expected,
                expected,
                expected,
                expected,
            ])

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
        historical_01661 = script.index("reference.py oracle 0.166.1")
        historical_01660 = script.index("reference.py oracle 0.166.0")
        historical_04392 = script.index("reference.py oracle 0.439.2")
        historical_01651 = script.index("reference.py oracle 0.165.1")
        historical_01660_source = script.index("reference.py source 0.166.0")
        historical_01661_source = script.index("reference.py source 0.166.1")
        historical_01661_suite = script.index("run_logged historical-python-01661 env ")
        historical_websocket = script.index("run_logged historical-websocket-fallback-sandbox-01660")
        historical_01660_suite = script.index("run_logged historical-python-01660 env ")
        historical_01660_tests = script[historical_01660_suite:script.index("\n", historical_01660_suite)]
        historical_04392_suite = script.index('run_logged historical-python-04392 "$PYTHON"')
        cross_release = script.index('run_logged historical-python-cross-release-01651-04392 "$PYTHON"')
        cross_release_tests = script[cross_release:script.index("\n", cross_release)]
        active_source = script.index("reference.py source active")
        historical_04392_source = script.index("reference.py source 0.439.2")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, active_suite)
        self.assertLess(active_source, active_suite)
        active_tests = script[active_suite:script.index("\n", active_suite)]
        self.assertIn("test_active_baseline_01662.py", active_tests)
        self.assertIn("test_hook_identity_01662.py", active_tests)
        self.assertIn("test_sub_agent_exec_help_01662.py", active_tests)
        self.assertIn("test_super_expose_help_01662.py", active_tests)
        self.assertIn("test_sub_agent_exec_diagnostics_01662.py", active_tests)
        self.assertIn("test_session_inspection_01662.py", active_tests)
        self.assertIn("test_ping_diagnostics_01662.py", active_tests)
        self.assertIn("test_logout_diagnostics_01662.py", active_tests)
        self.assertIn("test_doctor_install_01662.py", active_tests)
        self.assertIn("test_mcp_jsonl_bridge_help_precedence_01662.py", active_tests)
        self.assertIn("test_runtime_broker_help_precedence_01662.py", active_tests)

        self.assertIn("test_session_state_recovery_01662.py", active_tests)
        self.assertIn("test_profile_list_existing_empty_root_01662.py", active_tests)
        self.assertIn("test_info_status_offline_01662.py", active_tests)
        self.assertIn("test_provider_metadata_01662.py", active_tests)
        self.assertIn("test_provider_shapes_01662.py", active_tests)
        self.assertIn("test_provider_policy_codex_01662.py", active_tests)
        self.assertIn("test_deepseek_stream_ids_01662.py", active_tests)
        self.assertIn("test_local_compact_01662.py", active_tests)
        self.assertIn("test_guardian_api_key_01662.py", active_tests)
        self.assertFalse(any("01661" in test for test in unittest_files_for_lane(script, "focused-python-active")))
        self.assertLess(active_suite, historical_01661)
        self.assertLess(historical_01661_source, historical_01661_suite)
        self.assertLess(historical_01661, historical_01661_suite)
        historical_01661_tests = script[historical_01661_suite:script.index("\n", historical_01661_suite)]
        self.assertIn("test_active_baseline_01661.py", historical_01661_tests)
        self.assertIn("test_hook_identity_01661.py", historical_01661_tests)
        self.assertIn("test_sub_agent_exec_help_01661.py", historical_01661_tests)
        self.assertIn('env PRODEX_ORACLE="$PRODEX_ORACLE_01661" PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01661"', historical_01661_tests)
        self.assertLess(historical_01661_suite, historical_01660)
        self.assertLess(historical_01660_source, historical_01660_suite)
        self.assertLess(historical_01660, historical_01660_suite)
        self.assertLess(historical_01660_source, historical_websocket)
        self.assertLess(historical_websocket, historical_01660_suite)
        self.assertIn('env PRODEX_ORACLE="$PRODEX_ORACLE_01660" PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01660"', script)
        self.assertNotIn("test_ci_websocket_fallback_sandbox.py", active_tests)
        self.assertLess(historical_01660_suite, historical_04392)
        self.assertIn('run_logged historical-python-01660 env PRODEX_ORACLE="$PRODEX_ORACLE_01660"', script)
        self.assertIn('PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01660" MODEX_REFERENCE_DIR="$MODEX_REFERENCE_01660_DIR"', script)
        self.assertLess(active_suite, historical_04392_source)
        self.assertLess(historical_04392, historical_04392_suite)
        self.assertLess(historical_04392_source, historical_04392_suite)
        self.assertLess(historical_01651, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), active)
        self.assertLess(script.index("run_logged focused-build make build unit"), active)
        self.assertIn("test_active_baseline_01660.py", historical_01660_tests)
        self.assertIn("test_gateway_default_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_missing_message_content_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_custom_tool_calls_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_parent_shutdown_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_reasoning_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_stream_ids_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_catalog_01660.py", historical_01660_tests)
        self.assertIn("test_guardian_api_key_01660.py", historical_01660_tests)
        self.assertIn("test_policy_capacity_01660.py", historical_01660_tests)
        self.assertIn("test_provider_policy_codex_01660.py", historical_01660_tests)
        self.assertIn("test_provider_passthrough_01660.py", historical_01660_tests)
        self.assertIn("test_provider_shapes_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_stream_01660.py", historical_01660_tests)
        self.assertIn("test_root_help_errors_01660.py", historical_01660_tests)
        self.assertIn("test_super_cli_01660.py", historical_01660_tests)
        self.assertIn("test_runtime_broker_startup_01660_oracle.py", historical_01660_tests)
        self.assertIn("test_profile_list_empty_01660.py", historical_01660_tests)
        self.assertIn("test_session_outputs_01660.py", historical_01660_tests)
        historical_04392_tests = script[historical_04392_suite:script.index("\n", historical_04392_suite)]
        self.assertIn("test_cli.py", historical_04392_tests)
        self.assertIn("test_gateway_cli.py", historical_04392_tests)
        self.assertIn("test_session_text_memory_04392.py", historical_04392_tests)
        self.assertIn(
            'run_logged historical-python-cross-release-buffered-response-shapes env PRODEX_ORACLE_04392="$PRODEX_ORACLE_04392" PRODEX_ORACLE_01651="$PRODEX_ORACLE_01651" "$PYTHON" scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py',
            script,
        )
        self.assertIn("test_app_server_rpc_04392.py", historical_04392_tests)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", cross_release_tests)
        self.assertNotIn("test_anthropic_parent_shutdown_01660.py", cross_release_tests)
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
        for test_name in (
            "test_gateway_launch_01651.py", "test_local_rewrite_01651_oracle.py",
            "test_session_query_01651.py", "test_super_launch_01651.py",
            "test_super_dry_run_01651.py", "test_gateway_cli_01651.py",
            "test_profile_state_01651.py",
        ):
            self.assertNotIn(test_name, historical_tests)
        self.assertNotIn("historical-profile-state-01651", script)
        self.assertIn("historical-python-04395", script)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", script)
        self.assertIn("test_provider_catalog_04395.py", script)
        self.assertIn("test_runtime_binding_04395_slice.py", script)
        self.assertIn("test_session_04395_slice.py", script)
        self.assertIn("test_session_state_backup_04395.py", script)
        historical_04395_suite = script.index('run_logged historical-python-04395 "$PYTHON"')
        cross_04392_04395_suite = script.index('run_logged historical-python-cross-release-04392-04395 "$PYTHON"')
        historical_04395_tests = script[historical_04395_suite:script.index("\n", historical_04395_suite)]
        cross_04392_04395_tests = script[cross_04392_04395_suite:script.index("\n", cross_04392_04395_suite)]
        self.assertLess(historical_04395_suite, cross_04392_04395_suite)
        for test_name in (
            "test_provider_embedded_tool_calls_04395.py", "test_provider_nonstring_model_04395.py",
            "test_provider_request_tool_role_04395.py", "test_provider_request_untyped_content_04395.py",
            "test_session_04395_slice.py", "test_session_state_backup_04395.py",
        ):
            self.assertIn(test_name, cross_04392_04395_tests)
            self.assertNotIn(test_name, historical_04395_tests)
        self.assertIn("test_session_invalid_utf8_04392.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_resume.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_text.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_concurrency_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_session_profile_04392.py", script[cross_release:script.index("\n", cross_release)])
        for test_name in (
            "test_gateway_launch_01651.py", "test_local_rewrite_01651_oracle.py",
            "test_session_query_01651.py", "test_super_launch_01651.py",
            "test_super_dry_run_01651.py", "test_gateway_cli_01651.py",
            "test_profile_state_01651.py",
        ):
            self.assertIn(test_name, script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_super_subagent_model_shared.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_terminal_dimensions.py", script[cross_release:script.index("\n", cross_release)])
        self.assertIn("test_ci_parity_baseline.py", script)
        self.assertIn("run_logged historical-python-01651", script)
        self.assertIn("test_provider_stream_01651_characterization.py", script)
        self.assertIn("historical-04392-oracle: BLOCKED (required regression oracle unavailable; CI fails closed)", script)
        self.assertIn("historical-python-cross-release-01651-04392: BLOCKED", script)
        self.assertIn("Fast CI finished independent checks with a required historical lane blocked; overall CI fails closed.", script)
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
        historical_01661 = script.index("reference.py oracle 0.166.1")
        historical_01660 = script.index("reference.py oracle 0.166.0")
        historical_04392 = script.index("reference.py oracle 0.439.2")
        historical_01651 = script.index("reference.py oracle 0.165.1")
        historical_01660_source = script.index("reference.py source 0.166.0")
        historical_01661_source = script.index("reference.py source 0.166.1")
        historical_01661_suite = script.index("run_logged historical-python-01661 env ")
        historical_websocket = script.index("run_logged historical-websocket-fallback-sandbox-01660")
        historical_01660_suite = script.index("run_logged historical-python-01660 env ")
        historical_01660_tests = script[historical_01660_suite:script.index("\n", historical_01660_suite)]
        historical_04392_suite = script.index('run_logged historical-python-04392 "$PYTHON"')
        cross_release = script.index('run_logged historical-python-cross-release-01651-04392 "$PYTHON"')
        cross_release_tests = script[cross_release:script.index("\n", cross_release)]
        active_source = script.index("reference.py source active")
        historical_04392_source = script.index("reference.py source 0.439.2")
        active_suite = script.index("run_logged focused-python-active ")

        self.assertLess(active, active_suite)
        self.assertLess(active_source, active_suite)
        self.assertLess(script.index("run_logged build-input-check"), script.index("run_logged focused-build make build"))
        self.assertLess(script.index("run_logged focused-build make build unit"), active_suite)
        active_tests = script[active_suite:script.index("\n", active_suite)]
        self.assertIn("test_active_baseline_01662.py", active_tests)
        self.assertIn("test_hook_identity_01662.py", active_tests)
        self.assertIn("test_sub_agent_exec_help_01662.py", active_tests)
        self.assertIn("test_super_expose_help_01662.py", active_tests)
        self.assertIn("test_sub_agent_exec_diagnostics_01662.py", active_tests)
        self.assertIn("test_session_inspection_01662.py", active_tests)
        self.assertIn("test_ping_diagnostics_01662.py", active_tests)
        self.assertIn("test_logout_diagnostics_01662.py", active_tests)
        self.assertIn("test_doctor_install_01662.py", active_tests)
        self.assertIn("test_mcp_jsonl_bridge_help_precedence_01662.py", active_tests)
        self.assertIn("test_runtime_broker_help_precedence_01662.py", active_tests)

        self.assertIn("test_session_state_recovery_01662.py", active_tests)
        self.assertIn("test_profile_list_existing_empty_root_01662.py", active_tests)
        self.assertIn("test_info_status_offline_01662.py", active_tests)
        self.assertIn("test_provider_metadata_01662.py", active_tests)
        self.assertIn("test_provider_shapes_01662.py", active_tests)
        self.assertIn("test_provider_policy_codex_01662.py", active_tests)
        self.assertIn("test_deepseek_stream_ids_01662.py", active_tests)
        self.assertIn("test_local_compact_01662.py", active_tests)
        self.assertIn("test_guardian_api_key_01662.py", active_tests)
        self.assertFalse(any("01661" in test for test in unittest_files_for_lane(script, "focused-python-active")))
        self.assertLess(active_suite, historical_01661)
        self.assertLess(historical_01661_source, historical_01661_suite)
        self.assertLess(historical_01661, historical_01661_suite)
        historical_01661_tests = script[historical_01661_suite:script.index("\n", historical_01661_suite)]
        self.assertIn("test_active_baseline_01661.py", historical_01661_tests)
        self.assertIn("test_hook_identity_01661.py", historical_01661_tests)
        self.assertIn("test_sub_agent_exec_help_01661.py", historical_01661_tests)
        self.assertIn('env PRODEX_ORACLE="$PRODEX_ORACLE_01661" PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01661"', historical_01661_tests)
        self.assertLess(historical_01661_suite, historical_01660)
        self.assertLess(historical_01660_source, historical_01660_suite)
        self.assertLess(historical_01660, historical_01660_suite)
        self.assertLess(historical_01660_source, historical_websocket)
        self.assertLess(historical_websocket, historical_01660_suite)
        self.assertIn('env PRODEX_ORACLE="$PRODEX_ORACLE_01660" PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01660"', script)
        self.assertNotIn("test_ci_websocket_fallback_sandbox.py", active_tests)
        self.assertLess(historical_01660_suite, historical_04392)
        self.assertIn('run_logged historical-python-01660 env PRODEX_ORACLE="$PRODEX_ORACLE_01660"', script)
        self.assertIn('PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_01660" MODEX_REFERENCE_DIR="$MODEX_REFERENCE_01660_DIR"', script)
        self.assertLess(active_suite, historical_04392_source)
        self.assertLess(historical_04392, historical_04392_suite)
        self.assertLess(historical_04392_source, historical_04392_suite)
        self.assertLess(historical_01651, cross_release)
        self.assertLess(script.index("run_logged build-input-check"), historical_01651)
        self.assertLess(script.index("run_logged focused-build make build"), historical_01651)
        self.assertIn("test_active_baseline_01660.py", historical_01660_tests)
        self.assertIn("test_gateway_default_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_missing_message_content_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_custom_tool_calls_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_parent_shutdown_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_reasoning_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_stream_ids_01660.py", historical_01660_tests)
        self.assertIn("test_deepseek_catalog_01660.py", historical_01660_tests)
        self.assertIn("test_guardian_api_key_01660.py", historical_01660_tests)
        self.assertIn("test_policy_capacity_01660.py", historical_01660_tests)
        self.assertIn("test_provider_policy_codex_01660.py", historical_01660_tests)
        self.assertIn("test_runtime_broker_startup_01660_oracle.py", historical_01660_tests)
        self.assertIn("test_profile_list_empty_01660.py", historical_01660_tests)
        self.assertIn("test_session_outputs_01660.py", historical_01660_tests)
        self.assertIn("test_app_server_rpc_04392.py", script[historical_04392_suite:script.index("\n", historical_04392_suite)])
        self.assertIn("test_provider_passthrough_01660.py", historical_01660_tests)
        self.assertIn("test_provider_shapes_01660.py", historical_01660_tests)
        self.assertIn("test_anthropic_stream_01660.py", historical_01660_tests)
        self.assertIn("test_root_help_errors_01660.py", historical_01660_tests)
        self.assertIn("test_super_cli_01660.py", historical_01660_tests)
        self.assertIn(
            'run_logged historical-python-cross-release-buffered-response-shapes env PRODEX_ORACLE_04392="$PRODEX_ORACLE_04392" PRODEX_ORACLE_01651="$PRODEX_ORACLE_01651" "$PYTHON" scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py',
            script,
        )
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", script)
        self.assertIn("test_anthropic_stream_optional_metadata_shared.py", cross_release_tests)
        self.assertNotIn("test_anthropic_parent_shutdown_01660.py", cross_release_tests)
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
        self.assertIn("historical-python-04395", script)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", script)
        for test_name in (
            "test_gateway_launch_01651.py", "test_local_rewrite_01651_oracle.py",
            "test_session_query_01651.py", "test_super_launch_01651.py",
            "test_super_dry_run_01651.py", "test_gateway_cli_01651.py",
            "test_profile_state_01651.py",
        ):
            self.assertIn(test_name, script[cross_release:script.index("\n", cross_release)])
            self.assertNotIn(test_name, historical_tests)
        self.assertNotIn("historical-profile-state-01651", script)
        self.assertIn("test_provider_catalog_04395.py", script)
        self.assertIn("test_runtime_binding_04395_slice.py", script)
        self.assertIn("test_session_04395_slice.py", script)
        self.assertIn("test_session_state_backup_04395.py", script)
        self.assertIn("complete-suite: BLOCKED (required historical reference unavailable; no full-suite result claimed)", script)
        self.assertIn("Full CI finished independent checks with a required historical lane blocked; overall CI fails closed.", script)
        historical_04395_suite = script.index('run_logged historical-python-04395 "$PYTHON"')
        cross_04392_04395_suite = script.index('run_logged historical-python-cross-release-04392-04395 "$PYTHON"')
        historical_04395_tests = script[historical_04395_suite:script.index("\n", historical_04395_suite)]
        cross_04392_04395_tests = script[cross_04392_04395_suite:script.index("\n", cross_04392_04395_suite)]
        self.assertLess(historical_04395_suite, cross_04392_04395_suite)
        for test_name in (
            "test_provider_embedded_tool_calls_04395.py", "test_provider_nonstring_model_04395.py",
            "test_provider_request_tool_role_04395.py", "test_provider_request_untyped_content_04395.py",
            "test_session_04395_slice.py", "test_session_state_backup_04395.py",
        ):
            self.assertIn(test_name, cross_04392_04395_tests)
            self.assertNotIn(test_name, historical_04395_tests)
        self.assertIn("reference.py source 0.439.1", script)
        self.assertIn("reference.py source 0.165.1", script)
        self.assertIn('export PRODEX_ORACLE="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"', script)
        self.assertIn('reference.py oracle 0.439.2', script)
        self.assertIn('export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"', script)
        self.assertIn('export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-01651.txt")"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE"', script)
        self.assertIn('export PRODEX_GATEWAY_ORACLE_04392="$PRODEX_ORACLE_04392"', script)
        self.assertIn('export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"', script)

    def test_04395_lanes_follow_imported_oracle_fixture_dependencies(self):
        historical_04395 = {
            "test_ci_private_tmp_super_04395.py",
            "test_provider_catalog_04395.py",
            "test_runtime_binding_04395_slice.py",
        }
        cross_04392_04395 = {
            "test_provider_embedded_tool_calls_04395.py",
            "test_provider_nonstring_model_04395.py",
            "test_provider_request_tool_role_04395.py",
            "test_provider_request_untyped_content_04395.py",
            "test_session_04395_slice.py",
            "test_session_state_backup_04395.py",
        }
        self.assertTrue(test_uses_04392_cli_fixture("test_session_04395_slice.py"))

        for script_path in (ROOT / "scripts/ci/run-fast.sh", ROOT / "scripts/ci/run-full.sh"):
            with self.subTest(script=script_path.name):
                script = script_path.read_text(encoding="utf-8")
                historical = unittest_files_for_lane(script, "historical-python-04395")
                cross = unittest_files_for_lane(script, "historical-python-cross-release-04392-04395")
                self.assertEqual(historical, historical_04395)
                self.assertEqual(cross, cross_04392_04395)
                self.assertEqual(
                    {name for name in historical | cross if test_uses_04392_cli_fixture(name)},
                    cross,
                )

    def test_fast_and_full_focused_test_invocations_have_no_duplicate_files(self):
        for script_path in (ROOT / "scripts/ci/run-fast.sh", ROOT / "scripts/ci/run-full.sh"):
            with self.subTest(script=script_path.name):
                names = unittest_files(script_path.read_text(encoding="utf-8"))
                duplicates = {
                    name: count for name, count in collections.Counter(names).items() if count > 1
                }
                self.assertEqual(duplicates, {})

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

    def run_ci_with_fake_tools(
        self, script_name, *, missing_active=False, missing_04392_oracle=False,
        missing_04392_source=False, missing_04395_oracle=False,
    ):
        with tempfile.TemporaryDirectory(prefix="modex-ci-oracle-routing-") as temporary:
            temp = Path(temporary)
            root = temp / "repo"
            ci = root / "scripts/ci"
            ci.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/ci" / script_name, ci / script_name)
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

            active_oracle = temp / "oracle-01662"
            historical_01661_oracle = temp / "oracle-01661"
            historical_01660_oracle = temp / "oracle-01660"
            historical_04392_oracle = temp / "oracle-04392"
            historical_oracle = temp / "oracle-01651"
            later_historical_oracle = temp / "oracle-04395"
            for path in (active_oracle, historical_01661_oracle, historical_01660_oracle, historical_04392_oracle, historical_oracle, later_historical_oracle):
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
                "    oracle:0.166.1) printf 'reference\\toracle 0.166.1\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_HISTORICAL_01661_ORACLE\" ;;\n"
                "    oracle:0.166.0) printf 'reference\\toracle 0.166.0\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_HISTORICAL_01660_ORACLE\" ;;\n"
                "    oracle:active) printf 'reference\\toracle active\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_ACTIVE\" == 1 ]]; then echo 'synthetic missing Prodex 0.166.2 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_ACTIVE_ORACLE\" ;;\n"
                "    oracle:0.439.2) printf 'reference\\toracle 0.439.2\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04392_ORACLE\" == 1 ]]; then echo 'synthetic missing historical Prodex 0.439.2 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_HISTORICAL_04392_ORACLE\" ;;\n"
                "    oracle:0.165.1) printf 'reference\\toracle 0.165.1\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_HISTORICAL_ORACLE\" ;;\n"
                "    oracle:0.439.5) printf 'reference\\toracle 0.439.5\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04395_ORACLE\" == 1 ]]; then echo 'synthetic missing historical Prodex 0.439.5 oracle' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_LATER_HISTORICAL_ORACLE\" ;;\n"
                "    source:active) printf 'reference\\tsource active\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_SOURCE_ACTIVE\" ;;\n"
                "    source:0.166.1) printf 'reference\\tsource 0.166.1\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_SOURCE_01661\" ;;\n"
                "    source:0.166.0) printf 'reference\\tsource 0.166.0\\n' >>\"$FAKE_LOG\"; printf '%s\\n' \"$FAKE_SOURCE_01660\" ;;\n"
                "    source:0.439.2) printf 'reference\\tsource 0.439.2\\n' >>\"$FAKE_LOG\"; if [[ \"$FAKE_MISSING_04392_SOURCE\" == 1 ]]; then echo 'synthetic missing historical Prodex 0.439.2 source' >&2; exit 1; fi; printf '%s\\n' \"$FAKE_SOURCE_04392\" ;;\n"
                "    source:*) printf '%s\\n' \"$FAKE_SOURCE_ACTIVE\" ;;\n"
                "    identity:active) printf '{\"tag\":\"0.166.2\"}\\n' ;;\n"
                "    *) echo \"unexpected synthetic reference request: $*\" >&2; exit 2 ;;\n"
                "  esac\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && (\" $* \" == *' test_active_baseline_01662.py '* || \" $* \" == *' test_hook_identity_01662.py '* || \" $* \" == *' test_sub_agent_exec_help_01662.py '* || \" $* \" == *' test_sub_agent_exec_diagnostics_01662.py '* || \" $* \" == *' test_session_inspection_01662.py '* || \" $* \" == *' test_session_state_recovery_01662.py '* || \" $* \" == *' test_profile_list_existing_empty_root_01662.py '* || \" $* \" == *' test_info_status_offline_01662.py '* || \" $* \" == *' test_doctor_install_01662.py '*) ]]; then\n"
                "  printf 'active-test\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_ORACLE_01660-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE_01660-}\" \"${MODEX_REFERENCE_DIR-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_active_baseline_01661.py '* ]]; then\n"
                "  printf 'historical-01661-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${MODEX_REFERENCE_DIR-}\" \"${PRODEX_ORACLE_01661-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_active_baseline_01660.py '* ]]; then\n"
                "  printf 'historical-01660-test\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${MODEX_REFERENCE_DIR-}\" \"${PRODEX_ORACLE_01660-}\" \"${MODEX_REFERENCE_01660_DIR-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_profile_list_empty_01660.py '* ]]; then\n"
                "  printf 'profile-list-historical-test\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${MODEX_REFERENCE_DIR-}\" \"${PRODEX_ORACLE_01660-}\" >>\"$FAKE_LOG\"\n"
                "fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_ci_websocket_fallback_sandbox.py '* ]]; then\n"
                "  printf 'historical-websocket-sandbox\\t%s\\t%s\\t%s\\t%s\\n' \"${PRODEX_ORACLE-}\" \"${PRODEX_GATEWAY_ORACLE-}\" \"${MODEX_REFERENCE_DIR-}\" \"${MODEX_REFERENCE_VERSION-}\" >>\"$FAKE_LOG\"\n"
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
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_provider_catalog_04395.py '* ]]; then printf 'historical-04395-test\\n' >>\"$FAKE_LOG\"; fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_provider_embedded_tool_calls_04395.py '* ]]; then printf 'cross-04392-04395-test\\n' >>\"$FAKE_LOG\"; fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_text_memory.py '* ]]; then printf 'width-memory-independent-test\\n' >>\"$FAKE_LOG\"; fi\n"
                "if [[ \"${1-}\" == scripts/ci/run-unittest.py && \" $* \" == *' test_session_text_memory_04392.py '* ]]; then printf 'width-memory-parity-test\\n' >>\"$FAKE_LOG\"; fi\n"
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
                "FAKE_HISTORICAL_01661_ORACLE": str(historical_01661_oracle),
                "FAKE_HISTORICAL_01660_ORACLE": str(historical_01660_oracle),
                "FAKE_HISTORICAL_04392_ORACLE": str(historical_04392_oracle),
                "FAKE_HISTORICAL_ORACLE": str(historical_oracle),
                "FAKE_LATER_HISTORICAL_ORACLE": str(later_historical_oracle),
                "FAKE_SOURCE_ACTIVE": str(temp / "reference-source-01662"),
                "FAKE_SOURCE_01661": str(temp / "reference-source-01661"),
                "FAKE_SOURCE_01660": str(temp / "reference-source-01660"),
                "FAKE_SOURCE_04392": str(temp / "reference-source-04392"),
                "FAKE_LOG": str(events),
                "FAKE_MISSING_ACTIVE": "1" if missing_active else "0",
                "FAKE_MISSING_04392_ORACLE": "1" if missing_04392_oracle else "0",
                "FAKE_MISSING_04392_SOURCE": "1" if missing_04392_source else "0",
                "FAKE_MISSING_04395_ORACLE": "1" if missing_04395_oracle else "0",
                "MODEX_CI_ARTIFACT_PRODUCER": "1",
                "PRODEX_ORACLE": "/synthetic/inherited-old-oracle",
                "PRODEX_ORACLE_04392": "/synthetic/inherited-old-historical-oracle",
                "PRODEX_GATEWAY_ORACLE": "/synthetic/inherited-old-gateway-oracle",
                "PRODEX_GATEWAY_ORACLE_04392": "/synthetic/inherited-old-historical-gateway-oracle",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            result = subprocess.run(
                ["/bin/bash", str(ci / script_name)],
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
                str(historical_01661_oracle),
                str(historical_01660_oracle),
                str(historical_04392_oracle),
                str(historical_oracle),
            )

    def run_fast_with_fake_tools(
        self, *, missing_active, missing_04392_oracle=False, missing_04392_source=False,
        missing_04395_oracle=False,
    ):
        return self.run_ci_with_fake_tools(
            "run-fast.sh", missing_active=missing_active,
            missing_04392_oracle=missing_04392_oracle,
            missing_04392_source=missing_04392_source,
            missing_04395_oracle=missing_04395_oracle,
        )

    def run_full_with_fake_tools(
        self, *, missing_04392_oracle=False, missing_04392_source=False,
        missing_04395_oracle=False,
    ):
        return self.run_ci_with_fake_tools(
            "run-full.sh", missing_active=False,
            missing_04392_oracle=missing_04392_oracle,
            missing_04392_source=missing_04392_source,
            missing_04395_oracle=missing_04395_oracle,
        )

    def test_missing_active_oracle_still_builds_but_skips_oracle_tests_and_artifacts(self):
        result, events, summary, *_ = self.run_fast_with_fake_tools(missing_active=True)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing Prodex 0.166.2 oracle", result.stdout)
        active_reference = events.index("reference\toracle active")
        build_input_check = events.index("call\tscripts/ci/check-build-inputs.py")
        self.assertTrue(any(event.startswith("make\tbuild unit\t") for event in events))
        build_index = next(i for i, event in enumerate(events) if event.startswith("make\tbuild unit\t"))
        self.assertLess(build_input_check, build_index)
        self.assertLess(build_index, active_reference)
        self.assertFalse(any(event.startswith("active-test\t") for event in events))
        self.assertFalse(any(event.startswith("historical-01661-test\t") for event in events))
        self.assertFalse(any(event.startswith("historical-01660-test\t") for event in events))
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
        result, events, summary, *_ = self.run_fast_with_fake_tools(
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
        self.assertTrue(any(event.startswith("historical-test\t") for event in events))
        self.assertIn("historical-python-cross-release-01651-04392: BLOCKED", summary)
        self.assertIn("historical-python-01651: PASS", summary)
        self.assertIn("historical-python-04395: PASS", summary)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", summary)
        self.assertIn("Fast CI finished independent checks", summary)
        self.assertIn("historical-04395-test", events)
        self.assertIn("width-memory: PASS", summary)
        self.assertIn("width-memory-session-parity: BLOCKED", summary)
        self.assertIn("width-memory-independent-test", events)
        self.assertNotIn("width-memory-parity-test", events)
        self.assertNotIn("cross-04392-04395-test", events)
        self.assertLess(events.index("reference\toracle 0.439.2"), events.index("reference\toracle 0.165.1"))
        self.assertLess(events.index("reference\toracle 0.165.1"), next(i for i, event in enumerate(events) if event.startswith("historical-test\t")))

    def test_missing_historical_04392_source_fails_after_active_suite(self):
        result, events, summary, *_ = self.run_fast_with_fake_tools(
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
        self.assertTrue(any(event.startswith("historical-test\t") for event in events))
        self.assertIn("historical-python-cross-release-01651-04392: BLOCKED", summary)
        self.assertIn("historical-python-01651: PASS", summary)
        self.assertIn("historical-python-04395: PASS", summary)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", summary)
        self.assertIn("historical-04395-test", events)
        self.assertIn("width-memory: PASS", summary)
        self.assertIn("width-memory-session-parity: BLOCKED", summary)
        self.assertIn("width-memory-independent-test", events)
        self.assertNotIn("width-memory-parity-test", events)
        self.assertNotIn("cross-04392-04395-test", events)

    def test_missing_historical_04395_oracle_runs_independent_fast_checks_and_fails_closed(self):
        result, events, summary, *_ = self.run_fast_with_fake_tools(
            missing_active=False, missing_04395_oracle=True,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing historical Prodex 0.439.5 oracle", result.stdout)
        self.assertIn("historical-04395-oracle: BLOCKED", summary)
        self.assertIn("historical-python-04395: BLOCKED", summary)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", summary)
        self.assertIn("focused-python-active: PASS", summary)
        self.assertIn("focused-helper-python: PASS", summary)
        self.assertIn("width-memory: PASS", summary)
        self.assertIn("width-memory-parity-test", events)
        self.assertNotIn("width-memory-session-parity: BLOCKED", summary)
        self.assertIn("Fast CI finished independent checks", summary)
        self.assertNotIn("historical-04395-test", events)
        self.assertNotIn("cross-04392-04395-test", events)
        self.assertLess(events.index("reference\toracle 0.165.1"), events.index("reference\toracle 0.439.5"))

    def test_full_ci_runs_independent_lanes_when_04395_oracle_is_missing(self):
        result, events, summary, *_ = self.run_full_with_fake_tools(missing_04395_oracle=True)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("synthetic missing historical Prodex 0.439.5 oracle", result.stdout)
        self.assertIn("historical-04395-oracle: BLOCKED", summary)
        self.assertIn("historical-python-04395: BLOCKED", summary)
        self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", summary)
        self.assertIn("focused-python-active: PASS", summary)
        self.assertIn("independent-native-unit: PASS", summary)
        self.assertIn("supported-platform-probes: PASS", summary)
        self.assertIn("independent-width-memory: PASS", summary)
        self.assertIn("width-memory-session-parity: PASS", summary)
        self.assertIn("width-memory-parity-test", events)
        self.assertIn("capability-probes: PASS", summary)
        self.assertIn("complete-suite: BLOCKED", summary)
        self.assertIn("Full CI finished independent checks", summary)
        self.assertTrue(any(event.startswith("make\tprobes\t") for event in events))
        self.assertFalse(any(event.startswith("make\ttest\t") for event in events))
        self.assertNotIn("historical-04395-test", events)
        self.assertNotIn("cross-04392-04395-test", events)

    def test_full_ci_with_both_historical_oracles_missing_runs_units_once(self):
        result, events, summary, *_ = self.run_full_with_fake_tools(
            missing_04392_oracle=True, missing_04395_oracle=True,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("historical-04392-oracle: BLOCKED", summary)
        self.assertIn("historical-04395-oracle: BLOCKED", summary)
        self.assertIn("complete-suite: BLOCKED", summary)
        self.assertEqual(sum(event.startswith("make\tunit\t") for event in events), 1)
        self.assertIn("capability-probes: PASS", summary)

    def test_full_ci_runs_independent_lanes_and_fails_closed_without_04392_oracle_or_source(self):
        for missing in ("oracle", "source"):
            with self.subTest(missing=missing):
                options = {f"missing_04392_{missing}": True}
                result, events, summary, *_ = self.run_full_with_fake_tools(**options)

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("focused-python-active: PASS", summary)
                self.assertIn("independent-native-unit: PASS", summary)
                self.assertIn("historical-python-01651: PASS", summary)
                self.assertIn("historical-python-04395: PASS", summary)
                self.assertIn("historical-python-cross-release-04392-04395: BLOCKED", summary)
                self.assertIn("complete-suite: BLOCKED", summary)
                self.assertIn("independent-width-memory: PASS", summary)
                self.assertIn("width-memory-independent-test", events)
                self.assertIn("Full CI finished independent checks", summary)
                self.assertTrue(any(event.startswith("make\tunit\t") for event in events))
                self.assertTrue(any(event.startswith("make\tprobes\t") for event in events))
                self.assertFalse(any(event.startswith("make\ttest\t") for event in events))
                self.assertIn("historical-04395-test", events)
                self.assertNotIn("cross-04392-04395-test", events)
                if missing == "oracle":
                    self.assertIn("historical-04392-oracle: BLOCKED", summary)
                    self.assertIn("historical-04392-source: SKIPPED", summary)
                else:
                    self.assertIn("historical-04392-source: BLOCKED", summary)
                    self.assertIn("reference\tsource 0.439.2", events)
                self.assertIn("width-memory-session-parity: BLOCKED", summary)
                self.assertNotIn("width-memory-parity-test", events)

    def test_full_ci_runs_complete_suite_when_all_references_are_available(self):
        result, events, summary, *_ = self.run_full_with_fake_tools()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(event.startswith("make\ttest\t") for event in events))
        self.assertIn("complete-suite: PASS", summary)
        self.assertTrue(any(event.startswith("historical-04392-test\t") for event in events))
        self.assertIn("cross-release-test", "\n".join(events))
        self.assertNotIn("historical-04395-test", events)
        self.assertNotIn("cross-04392-04395-test", events)
        self.assertIn("Full CI checks passed.", result.stdout)

    def test_active_and_historical_suites_receive_their_pinned_oracles(self):
        (result, events, summary, active_oracle_path, historical_01661_oracle_path,
         historical_01660_oracle_path,
         historical_04392_oracle_path, historical_01651_oracle_path) = self.run_fast_with_fake_tools(missing_active=False)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(any(event.startswith("active-test\t") for event in events), f"events={events!r}; output={result.stdout}")
        active = next(event for event in events if event.startswith("active-test\t"))
        historical_01661 = next(
            event for event in events if event.startswith("historical-01661-test\t")
        )
        historical_01660 = next(
            event for event in events if event.startswith("historical-01660-test\t")
        )
        historical_websocket = next(
            event for event in events if event.startswith("historical-websocket-sandbox\t")
        )
        profile_list_historical = next(
            event for event in events if event.startswith("profile-list-historical-test\t")
        )
        historical_04392 = next(event for event in events if event.startswith("historical-04392-test\t"))
        cross_release = next(event for event in events if event.startswith("cross-release-test\t"))
        historical_01651 = next(event for event in events if event.startswith("historical-test\t"))
        active_test_index = next(i for i, event in enumerate(events) if event.startswith("active-test\t"))
        active_environment = active.split("\t")
        self.assertEqual(active_environment[1], active_oracle_path)
        self.assertEqual(active_environment[2], "")
        self.assertEqual(active_environment[3], active_oracle_path)
        self.assertEqual(active_environment[4], "")
        self.assertTrue(active_environment[5].endswith("reference-source-01662"))
        historical_01661_environment = historical_01661.split("\t")
        self.assertEqual(historical_01661_environment[1:3], [historical_01661_oracle_path] * 2)
        self.assertTrue(historical_01661_environment[3].endswith("reference-source-01661"))
        self.assertEqual(historical_01661_environment[4], historical_01661_oracle_path)
        historical_01660_environment = historical_01660.split("\t")
        self.assertEqual(historical_01660_environment[1:3], [historical_01660_oracle_path] * 2)
        self.assertTrue(historical_01660_environment[3].endswith("reference-source-01660"))
        self.assertEqual(historical_01660_environment[4], historical_01660_oracle_path)
        self.assertTrue(historical_01660_environment[5].endswith("reference-source-01660"))
        historical_websocket_environment = historical_websocket.split("\t")
        self.assertEqual(historical_websocket_environment[1:3], [historical_01660_oracle_path] * 2)
        self.assertTrue(historical_websocket_environment[3].endswith("reference-source-01660"))
        self.assertEqual(historical_websocket_environment[4], "0.166.0")
        profile_list_environment = profile_list_historical.split("\t")
        self.assertEqual(profile_list_environment[1:3], [historical_01660_oracle_path] * 2)
        self.assertTrue(profile_list_environment[3].endswith("reference-source-01660"))
        self.assertEqual(profile_list_environment[4], historical_01660_oracle_path)
        historical_04392_environment = historical_04392.split("\t")
        self.assertEqual(historical_04392_environment[1:5], [
            active_oracle_path,
            historical_04392_oracle_path,
            active_oracle_path,
            historical_04392_oracle_path,
        ])
        self.assertTrue(historical_04392_environment[5].endswith("reference-source-01662"))
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
        self.assertLess(events.index("reference\toracle active"), events.index(active))
        self.assertLess(events.index(active), events.index("reference\toracle 0.166.1"))
        self.assertLess(events.index("reference\toracle 0.166.1"), events.index(historical_01661))
        self.assertLess(events.index("reference\toracle 0.166.0"), events.index(historical_01660))
        self.assertLess(events.index("reference\tsource 0.166.0"), events.index(historical_01660))
        self.assertLess(events.index("reference\toracle 0.166.0"), events.index(historical_websocket))
        self.assertLess(events.index("reference\toracle active"), events.index(profile_list_historical))
        self.assertLess(active_test_index, events.index("reference\toracle 0.439.2"))
        historical_04392_test_index = events.index(next(
            event for event in events if event.startswith("historical-04392-test\t")
        ))
        self.assertLess(events.index("reference\toracle 0.439.2"), historical_04392_test_index)
        self.assertLess(events.index("reference\toracle 0.165.1"), events.index(cross_release))
        self.assertIn("historical-04395-test", events)
        self.assertIn("cross-04392-04395-test", events)
        self.assertIn("width-memory-independent-test", events)
        self.assertIn("width-memory-parity-test", events)
        self.assertIn("width-memory: PASS", summary)
        self.assertNotIn("width-memory-session-parity: BLOCKED", summary)
        self.assertLess(events.index("reference\toracle 0.439.5"), events.index("historical-04395-test"))
        self.assertLess(events.index("reference\toracle 0.439.5"), events.index("cross-04392-04395-test"))
        self.assertIn("Fast CI checks passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
