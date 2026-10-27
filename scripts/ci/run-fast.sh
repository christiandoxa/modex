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
"$PYTHON" scripts/ci/reference.py identity active >"$EVIDENCE_DIR/reference.json"
printf 'source_sha=%s\nmojo=%s\npython=%s\nreference_oracle_sha256=%s\n' \
    "$(git rev-parse HEAD)" "$($MOJO --version)" "$($PYTHON --version 2>&1)" \
    "$(sha256sum "$PRODEX_ORACLE" | cut -d ' ' -f1)" >"$EVIDENCE_DIR/identity.txt"
run_logged focused-build make build unit
run_logged focused-python "$PYTHON" scripts/ci/run-unittest.py test_cli.py test_ci_private_tmp_super_04395.py test_ci_python_path_resolution.py test_ci_test_census.py test_ci_unit_build_cache.py test_provider_catalog_04395.py test_provider_requests.py test_runtime.py test_session_04395_slice.py
echo 'Fast CI checks passed.' | tee -a "$EVIDENCE_DIR/summary.txt"
