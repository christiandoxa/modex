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
run_logged dependency-audit "$PYTHON" scripts/ci/check-product-dependencies.py
if ! "$PYTHON" scripts/ci/reference.py oracle >"$EVIDENCE_DIR/oracle-path.txt" 2>"$EVIDENCE_DIR/reference.log"; then
    cat "$EVIDENCE_DIR/reference.log" >&2
    exit 1
fi
cat "$EVIDENCE_DIR/reference.log"
echo 'reference: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
export PRODEX_ORACLE="$(cat "$EVIDENCE_DIR/oracle-path.txt")"
rm -- "$EVIDENCE_DIR/oracle-path.txt"
export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE"
if ! "$PYTHON" scripts/ci/reference.py oracle 0.439.5 >"$EVIDENCE_DIR/oracle-path-04395.txt" 2>"$EVIDENCE_DIR/reference-04395.log"; then
    cat "$EVIDENCE_DIR/reference-04395.log" >&2
    exit 1
fi
export PRODEX_ORACLE_04395="$(cat "$EVIDENCE_DIR/oracle-path-04395.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-04395.txt"
if ! "$PYTHON" scripts/ci/reference.py source 0.439.2 >"$EVIDENCE_DIR/reference-source-04392.txt" 2>"$EVIDENCE_DIR/reference-source-04392.log"; then
    cat "$EVIDENCE_DIR/reference-source-04392.log" >&2
    exit 1
fi
cat "$EVIDENCE_DIR/reference-source-04392.log"
export PRODEX_ORACLE_04392="$PRODEX_ORACLE"
export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"
rm -- "$EVIDENCE_DIR/reference-source-04392.txt"
"$PYTHON" scripts/ci/reference.py identity active >"$EVIDENCE_DIR/reference.json"
printf 'source_sha=%s\nmojo=%s\npython=%s\nreference_oracle_sha256=%s\n' \
    "$(git rev-parse HEAD)" "$($MOJO --version)" "$($PYTHON --version 2>&1)" \
    "$(sha256sum "$PRODEX_ORACLE" | cut -d ' ' -f1)" >"$EVIDENCE_DIR/identity.txt"
if [[ "${MODEX_CI_ARTIFACT_PRODUCER:-0}" == 1 ]]; then
    run_logged build-input-check "$PYTHON" scripts/ci/check-build-inputs.py
fi
run_logged focused-build make build unit
run_logged focused-python "$PYTHON" scripts/ci/run-unittest.py test_cli.py test_ci_build_input_cleanliness.py test_ci_private_tmp_super_04395.py test_ci_python_path_resolution.py test_ci_unit_build_cache.py test_ci_workflow_shards.py test_provider_catalog_04395.py test_provider_embedded_tool_calls_04395.py test_provider_nonstring_model_04395.py test_provider_request_tool_role_04395.py test_provider_request_untyped_content_04395.py test_provider_request_untyped_role_04392.py test_provider_tools_04392_characterization.py test_provider_requests.py test_runtime.py test_runtime_binding_04395_slice.py test_runtime_observer_04392.py test_runtime_observer_fuzz.py test_session_04395_slice.py
if [[ "${MODEX_CI_FAST_HELPER_TESTS_IN_CONSUMERS:-0}" == 1 ]]; then
    echo 'Fast CI helper tests are assigned to consumer shards.'
    printf 'focused-helper-python: SHARDED\n' | tee -a "$EVIDENCE_DIR/summary.txt"
else
    run_logged focused-helper-python "$PYTHON" scripts/ci/run-unittest.py test_ci_artifact_manifest.py test_ci_shard_runner.py test_ci_test_census.py
fi
run_logged width-memory env MODEX_WIDTH_MEMORY_ARTIFACTS="$EVIDENCE_DIR/width-memory" MODEX_WIDTH_MEMORY_DRIVER="$ROOT/build/tests/width_memory_driver" "$PYTHON" scripts/ci/run-unittest.py test_text_memory.py
echo 'Fast CI checks passed.' | tee -a "$EVIDENCE_DIR/summary.txt"
