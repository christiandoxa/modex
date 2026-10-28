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
if ! PRODEX_ORACLE="${PRODEX_ORACLE_01651:-}" "$PYTHON" scripts/ci/reference.py oracle active >"$EVIDENCE_DIR/oracle-path-active.txt" 2>"$EVIDENCE_DIR/reference.log"; then
    cat "$EVIDENCE_DIR/reference.log" >&2
    exit 1
fi
cat "$EVIDENCE_DIR/reference.log"
echo 'reference oracle: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
export PRODEX_ORACLE_01651="$(cat "$EVIDENCE_DIR/oracle-path-active.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-active.txt"
"$PYTHON" scripts/ci/reference.py identity active >"$EVIDENCE_DIR/reference.json"
export MODEX_REFERENCE_VERSION="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["tag"])' "$EVIDENCE_DIR/reference.json")"
printf 'source_sha=%s\nmojo=%s\npython=%s\nreference_commit=%s\nreference_oracle_01651_sha256=%s\n' \
    "$(git rev-parse HEAD)" "$($MOJO --version)" "$($PYTHON --version 2>&1)" \
    "$($PYTHON -c 'import json;print(json.load(open("docs/baseline.json"))["reference"]["commit"])')" \
    "$(sha256sum "$PRODEX_ORACLE_01651" | cut -d ' ' -f1)" >"$EVIDENCE_DIR/identity.txt"
run_logged build-input-check "$PYTHON" scripts/ci/check-build-inputs.py
run_logged focused-build make build
run_logged focused-python-01651 env -u PRODEX_ORACLE -u PRODEX_GATEWAY_ORACLE "$PYTHON" scripts/ci/run-unittest.py test_cli_01651.py test_provider_stream_01651_characterization.py test_session_query_01651.py test_local_rewrite_01651_oracle.py
if ! "$PYTHON" scripts/ci/reference.py oracle 0.439.2 >"$EVIDENCE_DIR/oracle-path-04392.txt" 2>"$EVIDENCE_DIR/reference-04392.log"; then
    cat "$EVIDENCE_DIR/reference-04392.log" >&2
    exit 1
fi
export PRODEX_ORACLE_04392="$(cat "$EVIDENCE_DIR/oracle-path-04392.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-04392.txt"
export PRODEX_ORACLE="$PRODEX_ORACLE_04392"
export PRODEX_GATEWAY_ORACLE="$PRODEX_ORACLE_04392"
printf 'reference_oracle_04392_sha256=%s\n' \
    "$(sha256sum "$PRODEX_ORACLE_04392" | cut -d ' ' -f1)" >>"$EVIDENCE_DIR/identity.txt"
if ! "$PYTHON" scripts/ci/reference.py oracle 0.439.5 >"$EVIDENCE_DIR/oracle-path-04395.txt" 2>"$EVIDENCE_DIR/reference-04395.log"; then
    cat "$EVIDENCE_DIR/reference-04395.log" >&2
    exit 1
fi
export PRODEX_ORACLE_04395="$(cat "$EVIDENCE_DIR/oracle-path-04395.txt")"
rm -- "$EVIDENCE_DIR/oracle-path-04395.txt"
if ! "$PYTHON" scripts/ci/reference.py source active >"$EVIDENCE_DIR/reference-source-active.txt" 2>"$EVIDENCE_DIR/reference-source-active.log"; then
    cat "$EVIDENCE_DIR/reference-source-active.log" >&2
    exit 1
fi
if ! "$PYTHON" scripts/ci/reference.py source 0.439.1 >"$EVIDENCE_DIR/reference-source-04391.txt" 2>"$EVIDENCE_DIR/reference-source-04391.log"; then
    cat "$EVIDENCE_DIR/reference-source-04391.log" >&2
    exit 1
fi
if ! "$PYTHON" scripts/ci/reference.py source 0.439.2 >"$EVIDENCE_DIR/reference-source-04392.txt" 2>"$EVIDENCE_DIR/reference-source-04392.log"; then
    cat "$EVIDENCE_DIR/reference-source-04392.log" >&2
    exit 1
fi
export MODEX_REFERENCE_DIR="$(cat "$EVIDENCE_DIR/reference-source-active.txt")"
export MODEX_REFERENCE_04392_DIR="$(cat "$EVIDENCE_DIR/reference-source-04392.txt")"
export MODEX_REFERENCE_04391_DIR="$(cat "$EVIDENCE_DIR/reference-source-04391.txt")"
cat "$EVIDENCE_DIR/reference-source-active.log" "$EVIDENCE_DIR/reference-source-04391.log" "$EVIDENCE_DIR/reference-source-04392.log"
echo 'reference sources: PASS' | tee -a "$EVIDENCE_DIR/summary.txt"
rm -- "$EVIDENCE_DIR/reference-source-active.txt" "$EVIDENCE_DIR/reference-source-04391.txt" "$EVIDENCE_DIR/reference-source-04392.txt"
run_logged supported-platform-probes make probes
run_logged complete-suite make test
run_logged capability-probes "$PYTHON" tests/probe_capabilities.py
echo 'Full CI checks passed.' | tee -a "$EVIDENCE_DIR/summary.txt"
