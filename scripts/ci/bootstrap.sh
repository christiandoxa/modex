#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || {
    echo 'Python 3.14+ is required to bootstrap CI.' >&2
    exit 1
}
PYTHON_MINOR="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
TOOLCHAIN_DIR="${MODEX_TOOLCHAIN_DIR:-${HOME}/.cache/modex/toolchains/mojo-1.2.0/linux-x86_64-py${PYTHON_MINOR}}"
EXPECTED_MOJO='Mojo 1.2.0 (2016d0cd)'

check_platform() {
    [[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
        echo 'CI bootstrap currently supports Linux x86-64 only.' >&2
        return 1
    }
}

check_flock() {
    local flock_bin
    flock_bin="$(command -v flock || true)"
    [[ -n "$flock_bin" && -x "$flock_bin" ]] || {
        echo 'util-linux flock is required to serialize cached unit builds.' >&2
        return 1
    }
    local help
    help="$("$flock_bin" --help 2>&1 || true)"
    [[ "$help" == *"--close"* ]] || {
        echo 'flock with --close support is required to prevent child processes from retaining the unit-build lock.' >&2
        return 1
    }
    printf 'flock (%s); --close supported\n' "$(readlink -f -- "$flock_bin")"
}

check_python() {
    "$PYTHON" - "${MODEX_CI_PYTHON_VERSION:-}" <<'PY'
import sys
try:
    import compression.zstd
except ImportError as error:
    raise SystemExit(f"Python 3.14+ with stdlib compression.zstd is required: {error}")
if sys.version_info < (3, 14):
    raise SystemExit(f"Python 3.14+ is required; found {sys.version.split()[0]}")
expected = sys.argv[1] if len(sys.argv) > 1 else ""
if expected:
    try:
        expected_version = tuple(int(part) for part in expected.split("."))
    except ValueError as error:
        raise SystemExit(f"invalid pinned Python version: {expected}") from error
    if sys.version_info[:len(expected_version)] != expected_version:
        raise SystemExit(f"Python {expected} is required; found {sys.version.split()[0]}")
print(f"Python {sys.version.split()[0]} ({sys.executable}); compression.zstd available")
PY
}

check_bwrap() {
    local bwrap_bin="${BWRAP:-bwrap}"
    command -v "$bwrap_bin" >/dev/null 2>&1 || {
        echo 'bubblewrap is required; run scripts/ci/ensure-bwrap.sh first.' >&2
        return 1
    }
    "$bwrap_bin" --unshare-all --die-with-parent --new-session \
        --ro-bind / / --proc /proc --dev /dev --tmpfs /tmp -- /usr/bin/true || {
        echo 'bubblewrap is installed, but the required user/mount/PID/network namespace operation failed.' >&2
        return 1
    }
    printf '%s; namespace probe passed\n' "$("$bwrap_bin" --version)"
}

check_mojo() {
    local mojo_bin="${MOJO_BIN:-${MOJO:-${TOOLCHAIN_DIR}/bin/mojo}}"
    if ! command -v "$mojo_bin" >/dev/null 2>&1; then
        mojo_bin="$(command -v mojo || true)"
    fi
    [[ -n "$mojo_bin" ]] || {
        echo 'Mojo is missing; run make ci-bootstrap to acquire the pinned official compiler.' >&2
        return 1
    }
    local actual
    actual="$("$mojo_bin" --version)"
    [[ "$actual" == "$EXPECTED_MOJO" ]] || {
        printf 'Pinned toolchain required: %s; found: %s\n' "$EXPECTED_MOJO" "$actual" >&2
        return 1
    }
    printf '%s (%s)\n' "$actual" "$(readlink -f -- "$mojo_bin")"
}

write_evidence() {
    local evidence_dir="${CI_EVIDENCE_DIR:-}"
    [[ -n "$evidence_dir" ]] || return 0
    mkdir -p -- "$evidence_dir"
    {
        check_platform
        check_python
        check_mojo
        check_bwrap
        check_flock
    } >"$evidence_dir/bootstrap.txt" 2>&1
}

case "${1:---check}" in
    --check)
        check_platform
        check_python
        check_mojo
        check_bwrap
        check_flock
        write_evidence
        ;;
    --install-mojo)
        check_platform
        check_python
        check_flock
        mkdir -p -- "$TOOLCHAIN_DIR"
        if [[ ! -x "$TOOLCHAIN_DIR/bin/python" ]]; then
            "$PYTHON" -m venv "$TOOLCHAIN_DIR"
        fi
        "$TOOLCHAIN_DIR/bin/python" -m pip install \
            --no-cache-dir --no-deps --force-reinstall --only-binary=:all: --require-hashes \
            -r "$ROOT/scripts/ci/mojo-linux-x86_64.txt"
        if [[ -n "${GITHUB_PATH:-}" ]]; then
            printf '%s\n' "$TOOLCHAIN_DIR/bin" >>"$GITHUB_PATH"
        fi
        MOJO_BIN="$TOOLCHAIN_DIR/bin/mojo" check_mojo
        check_bwrap
        write_evidence
        ;;
    *)
        echo 'usage: scripts/ci/bootstrap.sh [--check|--install-mojo]' >&2
        exit 2
        ;;
esac
