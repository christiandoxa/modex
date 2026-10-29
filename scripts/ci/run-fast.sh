#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || {
    echo 'Python 3.14+ is required to run fast CI.' >&2
    exit 1
}
PYTHON="$(realpath -e -- "$(command -v "$PYTHON")")"
PYTHON_MINOR="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
TOOLCHAIN_DIR="${MODEX_TOOLCHAIN_DIR:-${HOME}/.cache/modex/toolchains/mojo-1.2.0/linux-x86_64-py${PYTHON_MINOR}}"
EVIDENCE_DIR="${CI_EVIDENCE_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/modex-ci-evidence}"
MODEX_REFERENCE_CACHE="${MODEX_REFERENCE_CACHE:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/modex-reference-cache}"
mkdir -p -- "$EVIDENCE_DIR"
cd -- "$ROOT"
TOOLCHAIN_DIR="$(realpath -m -- "$TOOLCHAIN_DIR")"
source scripts/ci/private-scratch.sh

run_logged() {
    local name="$1"
    shift
    set +e
    "$@" 2>&1 | tee "$EVIDENCE_DIR/$name.log"
    local result="${PIPESTATUS[0]}"
    set -e
    printf '%s: %s\n' "$name" "$([[ "$result" == 0 ]] && echo PASS || echo FAIL)" | tee -a "$EVIDENCE_DIR/summary.txt"
    return "$result"
}

BWRAP="$(scripts/ci/ensure-bwrap.sh)"
export BWRAP
export PATH="$(dirname -- "$BWRAP"):$PATH"
export MODEX_TOOLCHAIN_DIR="$TOOLCHAIN_DIR"
export MODEX_REFERENCE_CACHE
export PYTHON
run_logged bootstrap scripts/ci/bootstrap.sh --install-mojo
export MOJO="$TOOLCHAIN_DIR/bin/mojo"
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
run_logged prerequisites scripts/ci/bootstrap.sh --check
run_logged workflow-validation scripts/ci/validate-workflows.sh
run_logged policy-helper-tests "$PYTHON" scripts/ci/run-unittest.py test_ci_workflow_policy.py test_ci_product_dependencies.py test_ci_oracle_routing.py test_ci_parity_baseline.py
run_logged dependency-audit "$PYTHON" scripts/ci/check-product-dependencies.py
run_logged reference-helper-tests "$PYTHON" scripts/ci/run-unittest.py test_ci_reference.py
if [[ "${MODEX_CI_ARTIFACT_PRODUCER:-0}" == 1 ]]; then
    run_logged build-input-check "$PYTHON" scripts/ci/check-build-inputs.py
fi
run_logged focused-build make build unit
if ! "$PYTHON" scripts/ci/reference.py oracle active >"$EVIDENCE_DIR/oracle-path-active.txt" 2>"$EVIDENCE_DIR/reference.log"; then
    cat "$EVIDENCE_DIR/reference.log" >&2
    exit 1
fi
cat "$EVIDENCE_DIR/reference.log"
echo 'reference: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"
export PRODEX_ORACLE="$PRODEX_ORACLE_04392"
export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"
rm -- "$EVIDENCE_DIR/oracle-path-active.txt"
if ! "$PYTHON" scripts/ci/reference.py source active >"$EVIDENCE_DIR/reference-source-active.txt" 2>"$EVIDENCE_DIR/reference-source-active.log"; then
    cat "$EVIDENCE_DIR/reference-source-active.log" >&2
    exit 1
fi
export MODEX_REFERENCE_DIR="$(cat "$EVIDENCE_DIR/reference-source-active.txt")"
export MODEX_REFERENCE_04392_DIR="$MODEX_REFERENCE_DIR"
cat "$EVIDENCE_DIR/reference-source-active.log"
rm -- "$EVIDENCE_DIR/reference-source-active.txt"
printf 'source_sha=%s\nreference_commit=%s\nmojo=%s\npython=%s\nreference_oracle_04392_sha256=%s\n' \
    "$(git rev-parse HEAD)" "$($PYTHON -c 'import json;print(json.load(open("docs/baseline.json"))["reference"]["commit"])')" \
    "$($MOJO --version)" "$($PYTHON --version 2>&1)" \
    "$(sha256sum "$PRODEX_ORACLE_04392" | cut -d ' ' -f1)" >"$EVIDENCE_DIR/identity.txt"
run_logged focused-python-active "$PYTHON" scripts/ci/run-unittest.py test_anthropic_buffered_payload_04392.py test_anthropic_message_arrays_04392.py test_anthropic_text_stream_04392.py test_app_server_rpc_04392.py test_cli.py test_ci_build_input_cleanliness.py test_ci_python_path_resolution.py test_ci_unit_build_cache.py test_continuation_binding_04392.py test_deepseek_web_search_mode_04392.py test_gateway_cli.py test_local_rewrite_04392_oracle.py test_profile_cli.py test_provider_request_untyped_role_04392.py test_provider_tools_04392_characterization.py test_provider_requests.py test_runtime.py test_runtime_observer_04392.py test_runtime_observer_fuzz.py test_super_probe_diagnostic_04392.py
run_logged focused-relay-python "$PYTHON" scripts/ci/run-unittest.py test_local_rewrite.py test_loopback_server.py
if ! PRODEX_ORACLE="${PRODEX_ORACLE_01651:-}" "$PYTHON" scripts/ci/reference.py oracle 0.165.1 >"$EVIDENCE_DIR/oracle-path-01651.txt" 2>"$EVIDENCE_DIR/reference-01651.log"; then
    cat "$EVIDENCE_DIR/reference-01651.log" >&2
    exit 1
fi
export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-01651.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-01651.txt"
run_logged focused-python-active-cross-release "$PYTHON" scripts/ci/run-unittest.py test_anthropic_stream_optional_metadata_shared.py test_provider_stream_repeated_search_04392.py test_session_invalid_utf8_04392.py test_session_resume.py test_super_concurrency_shared.py test_session_profile_04392.py test_super_subagent_model_shared.py test_terminal_dimensions.py
run_logged historical-python-01651 env -u PRODEX_ORACLE -u PRODEX_GATEWAY_ORACLE "$PYTHON" scripts/ci/run-unittest.py test_cli_01651.py test_gateway_cli_01651.py test_provider_stream_01651_characterization.py test_anthropic_mixed_tools_01651.py test_session_query_01651.py test_unicode_case_properties.py test_session_report_01651.py test_log_01651.py test_local_rewrite_01651_oracle.py test_runtime_proxy_websocket_01651_oracle.py test_app_server_rpc_01651.py test_super_model_toml_01651.py test_super_launch_01651.py
if ! "$PYTHON" scripts/ci/reference.py oracle 0.439.5 >"$EVIDENCE_DIR/oracle-path-04395.txt" 2>"$EVIDENCE_DIR/reference-04395.log"; then
    cat "$EVIDENCE_DIR/reference-04395.log" >&2
    exit 1
fi
export PRODEX_ORACLE_04395="$(cat "$EVIDENCE_DIR/oracle-path-04395.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-04395.txt"
"$PYTHON" scripts/ci/reference.py identity active >"$EVIDENCE_DIR/reference.json"
run_logged historical-python-04395 "$PYTHON" scripts/ci/run-unittest.py test_ci_private_tmp_super_04395.py test_provider_catalog_04395.py test_provider_embedded_tool_calls_04395.py test_provider_nonstring_model_04395.py test_provider_request_tool_role_04395.py test_provider_request_untyped_content_04395.py test_runtime_binding_04395_slice.py test_session_04395_slice.py test_session_state_backup_04395.py
if [[ "${MODEX_CI_FAST_HELPER_TESTS_IN_SHARDS:-0}" == 1 ]]; then
    echo 'Fast CI helper tests are assigned to independent shards.'
    printf 'focused-helper-python: SHARDED\n' | tee -a "$EVIDENCE_DIR/summary.txt"
else
    run_logged focused-helper-python "$PYTHON" scripts/ci/run-unittest.py test_ci_artifact_manifest.py test_ci_private_scratch.py test_ci_shard_runner.py test_ci_test_census.py test_ci_workflow_shards.py
fi
run_logged width-memory env MODEX_WIDTH_MEMORY_ARTIFACTS="$EVIDENCE_DIR/width-memory" MODEX_WIDTH_MEMORY_DRIVER="$ROOT/build/tests/width_memory_driver" "$PYTHON" scripts/ci/run-unittest.py test_text_memory.py
echo 'Fast CI checks passed.' | tee -a "$EVIDENCE_DIR/summary.txt"
