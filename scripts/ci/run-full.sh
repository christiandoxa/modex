#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || {
    echo 'Python 3.14+ is required to run full CI.' >&2
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
if [[ -L "$ROOT/build" ]]; then
    echo "Full CI requires a normal $ROOT/build directory; symlinked build paths are unsupported." >&2
    exit 2
fi
EXPECTED_BUILD_DIR="$(realpath -m -- "$ROOT/build")"
BUILD_DIR="${BUILD_DIR:-$EXPECTED_BUILD_DIR}"
case "$BUILD_DIR" in
    /*) ;;
    *) BUILD_DIR="$ROOT/$BUILD_DIR" ;;
esac
BUILD_DIR="$(realpath -m -- "$BUILD_DIR")"
if [[ "$BUILD_DIR" != "$EXPECTED_BUILD_DIR" ]]; then
    echo "Full CI Python tests require BUILD_DIR=$EXPECTED_BUILD_DIR; other tests use ROOT/build directly." >&2
    exit 2
fi
source scripts/ci/private-scratch.sh
export MODEX_REFERENCE_CACHE
export BUILD_DIR

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
export PYTHON
run_logged bootstrap scripts/ci/bootstrap.sh --install-mojo
export MOJO="$TOOLCHAIN_DIR/bin/mojo"
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
run_logged prerequisites scripts/ci/bootstrap.sh --check
run_logged workflow-validation scripts/ci/validate-workflows.sh
run_logged dependency-audit "$PYTHON" scripts/ci/check-product-dependencies.py
run_logged test-census "$PYTHON" scripts/ci/check-test-census.py
if ! "$PYTHON" scripts/ci/reference.py oracle active >"$EVIDENCE_DIR/oracle-path-active.txt" 2>"$EVIDENCE_DIR/reference-active.log"; then
    cat "$EVIDENCE_DIR/reference-active.log" >&2
    exit 1
fi
cat "$EVIDENCE_DIR/reference-active.log"
echo 'active reference oracle: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
export PRODEX_ORACLE="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"
export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE"
rm -- "$EVIDENCE_DIR/oracle-path-active.txt"
if ! "$PYTHON" scripts/ci/reference.py source active >"$EVIDENCE_DIR/reference-source-active.txt" 2>"$EVIDENCE_DIR/reference-source-active.log"; then
    cat "$EVIDENCE_DIR/reference-source-active.log" >&2
    exit 1
fi
export MODEX_REFERENCE_DIR="$(cat "$EVIDENCE_DIR/reference-source-active.txt")"
cat "$EVIDENCE_DIR/reference-source-active.log"
rm -- "$EVIDENCE_DIR/reference-source-active.txt"
"$PYTHON" scripts/ci/reference.py identity active >"$EVIDENCE_DIR/reference.json"
export MODEX_REFERENCE_VERSION="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["tag"])' "$EVIDENCE_DIR/reference.json")"
run_logged build-input-check "$PYTHON" scripts/ci/check-build-inputs.py
run_logged focused-build make build
run_logged focused-python-active env -u PRODEX_ORACLE_04392 -u PRODEX_GATEWAY_ORACLE_04392 -u MODEX_REFERENCE_04392_DIR "$PYTHON" scripts/ci/run-unittest.py test_active_baseline_01660.py test_gateway_default_01660.py test_deepseek_reasoning_01660.py test_policy_capacity_01660.py test_runtime_broker_startup_01660_oracle.py
if ! PRODEX_ORACLE_04392="${PRODEX_ORACLE_04392:-}" "$PYTHON" scripts/ci/reference.py oracle 0.439.2 >"$EVIDENCE_DIR/oracle-path-04392.txt" 2>"$EVIDENCE_DIR/reference-04392.log"; then
    cat "$EVIDENCE_DIR/reference-04392.log" >&2
    echo 'historical-04392-oracle: BLOCKED (required regression oracle unavailable; CI fails closed)' | tee -a "$EVIDENCE_DIR/summary.txt"
    exit 1
fi
export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"
export PRODEX_GATEWAY_ORACLE_04392="$PRODEX_ORACLE_04392"
rm -- "$EVIDENCE_DIR/oracle-path-04392.txt"
if ! "$PYTHON" scripts/ci/reference.py source 0.439.2 >"$EVIDENCE_DIR/reference-source-04392.txt" 2>"$EVIDENCE_DIR/reference-source-04392.log"; then
    cat "$EVIDENCE_DIR/reference-source-04392.log" >&2
    echo 'historical-04392-source: BLOCKED (required regression source unavailable; CI fails closed)' | tee -a "$EVIDENCE_DIR/summary.txt"
    exit 1
fi
export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"
cat "$EVIDENCE_DIR/reference-source-04392.log"
rm -- "$EVIDENCE_DIR/reference-source-04392.txt"
printf 'source_sha=%s\nmojo=%s\npython=%s\nreference_commit=%s\nreference_oracle_sha256=%s\nreference_oracle_04392_sha256=%s\n' \
    "$(git rev-parse HEAD)" "$($MOJO --version)" "$($PYTHON --version 2>&1)" \
    "$($PYTHON -c 'import json;print(json.load(open("docs/baseline.json"))["reference"]["commit"])')" \
    "$(sha256sum "$PRODEX_ORACLE" | cut -d ' ' -f1)" \
    "$(sha256sum "$PRODEX_ORACLE_04392" | cut -d ' ' -f1)" >"$EVIDENCE_DIR/identity.txt"
run_logged historical-python-04392 "$PYTHON" scripts/ci/run-unittest.py test_app_server_rpc_04392.py
if ! "$PYTHON" scripts/ci/reference.py oracle 0.165.1 >"$EVIDENCE_DIR/oracle-path-01651.txt" 2>"$EVIDENCE_DIR/reference-01651.log"; then
    cat "$EVIDENCE_DIR/reference-01651.log" >&2
    exit 1
fi
export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-01651.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-01651.txt"
run_logged historical-python-cross-release-buffered-response-shapes env PRODEX_ORACLE_04392="$PRODEX_ORACLE_04392" PRODEX_ORACLE_01651="$PRODEX_ORACLE_01651" "$PYTHON" scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py
run_logged historical-python-cross-release-01651-04392 "$PYTHON" scripts/ci/run-unittest.py test_runtime_proxy_websocket_04392_oracle.py test_anthropic_mixed_tools_01651.py test_anthropic_orphan_result_01651_04392.py test_anthropic_request_max_output_tokens_01651.py test_anthropic_request_unknown_fields_01651_04392.py test_anthropic_request_sampling_01651_04392.py test_anthropic_websearch_json_mode_01651_04392.py test_deepseek_web_search_mode_01651_04392.py test_deepseek_key_rotation_01651_04392.py test_deepseek_session_history_isolation_01651_04392.py test_provider_buffered_choice_01651_04392.py test_provider_request_prepare.py test_super_enum_values_01651_04392.py test_super_shared_config_01651_04392.py test_anthropic_stream_optional_metadata_shared.py test_provider_stream_repeated_search_04392.py test_provider_stream_cross_release_characterization.py test_loopback_header_whitespace.py test_log_stream_escaped_event_01651_04392.py test_log_upstream_selection_01651_04392.py test_log_token_selection_01651_04392.py test_log_plain_parser_01651_04392.py test_log_tty_fallback.py test_log_endpoint_projection_01651_04392.py test_log_redaction_01651_04392.py test_runtime_slow_partial.py test_session_generated_stateless_matrix.py test_session_cli.py test_session_invalid_utf8_04392.py test_session_resume.py test_session_text.py test_super_concurrency_shared.py test_session_profile_04392.py test_super_subagent_model_shared.py test_terminal_dimensions.py
run_logged historical-python-01651 env -u PRODEX_ORACLE -u PRODEX_GATEWAY_ORACLE "$PYTHON" scripts/ci/run-unittest.py test_cli_01651.py test_gateway_cli_01651.py test_gateway_launch_01651.py test_provider_stream_01651_characterization.py test_session_query_01651.py test_local_rewrite_01651_oracle.py test_runtime_proxy_websocket_01651_oracle.py test_app_server_rpc_01651.py test_super_model_toml_01651.py test_super_launch_01651.py test_super_dry_run_01651.py
run_logged historical-profile-state-01651 env -u PRODEX_ORACLE -u PRODEX_GATEWAY_ORACLE "$PYTHON" scripts/ci/run-unittest.py test_profile_state_01651.py
if ! "$PYTHON" scripts/ci/reference.py oracle 0.439.5 >"$EVIDENCE_DIR/oracle-path-04395.txt" 2>"$EVIDENCE_DIR/reference-04395.log"; then
    cat "$EVIDENCE_DIR/reference-04395.log" >&2
    exit 1
fi
export PRODEX_ORACLE_04395="$(cat "$EVIDENCE_DIR/oracle-path-04395.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-04395.txt"
if ! "$PYTHON" scripts/ci/reference.py source 0.439.1 >"$EVIDENCE_DIR/reference-source-04391.txt" 2>"$EVIDENCE_DIR/reference-source-04391.log"; then
    cat "$EVIDENCE_DIR/reference-source-04391.log" >&2
    exit 1
fi
if ! "$PYTHON" scripts/ci/reference.py source 0.165.1 >"$EVIDENCE_DIR/reference-source-01651.txt" 2>"$EVIDENCE_DIR/reference-source-01651.log"; then
    cat "$EVIDENCE_DIR/reference-source-01651.log" >&2
    exit 1
fi
export MODEX_REFERENCE_04391_DIR="$(cat "$EVIDENCE_DIR/reference-source-04391.txt")"
export MODEX_REFERENCE_01651_DIR="$(cat "$EVIDENCE_DIR/reference-source-01651.txt")"
cat "$EVIDENCE_DIR/reference-source-04391.log" "$EVIDENCE_DIR/reference-source-01651.log"
echo 'reference sources: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
rm -- "$EVIDENCE_DIR/reference-source-04391.txt" "$EVIDENCE_DIR/reference-source-01651.txt"
run_logged supported-platform-probes make probes
run_logged complete-suite make test
run_logged capability-probes "$PYTHON" tests/probe_capabilities.py
echo 'Full CI checks passed.' | tee -a "$EVIDENCE_DIR/summary.txt"
