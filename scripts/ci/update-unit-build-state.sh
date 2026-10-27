#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 5 ]]; then
    echo 'usage: update-unit-build-state.sh state-path mojo version flags includes' >&2
    exit 2
fi

state_path="$1"
mojo_command="$2"
expected_version="$3"
mojo_flags="$4"
include_flags="$5"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd -- "$root"

mojo_path="$(command -v "$mojo_command" 2>/dev/null || true)"
[[ -n "$mojo_path" && -x "$mojo_path" ]] || {
    echo "Mojo compiler is not executable: $mojo_command" >&2
    exit 1
}
mojo_path="$(realpath -e -- "$mojo_path")"
actual_version="$("$mojo_path" --version)"
[[ "$actual_version" == "$expected_version" ]] || {
    printf 'Pinned toolchain required: %s; found: %s\n' "$expected_version" "$actual_version" >&2
    exit 1
}

source_symlink="$(find src tests -type l -print -quit)"
[[ -z "$source_symlink" ]] || {
    echo "Unit build caching does not support symlinked Mojo sources/imports: $source_symlink" >&2
    exit 1
}

toolchain_root="$(dirname -- "$(dirname -- "$mojo_path")")"
shopt -s nullglob
package_roots=("$toolchain_root"/lib/python*/site-packages)
mojo_packages=()
for package_root in "${package_roots[@]}"; do
    if [[ -d "$package_root/modular" && -d "$package_root/mojo" ]]; then
        resolved_package_root="$(realpath -e -- "$package_root")"
        [[ "$resolved_package_root" == "$package_root" ]] || {
            echo "Unit build caching does not support symlinked toolchain package roots: $package_root" >&2
            exit 1
        }
        mojo_packages+=("$package_root/modular" "$package_root/mojo")
    fi
done
[[ ${#mojo_packages[@]} -gt 0 ]] || {
    echo "Cannot identify the Mojo compiler and standard library under $toolchain_root." >&2
    exit 1
}
for package in "${mojo_packages[@]}"; do
    package_symlink="$(find "$package" -type l -print -quit)"
    [[ -z "$package_symlink" ]] || {
        echo "Unit build caching does not support symlinked compiler/stdlib files: $package_symlink" >&2
        exit 1
    }
done

interpreter_path=""
if [[ "$(od -An -N2 -t x1 -- "$mojo_path" | tr -d ' \n')" == 2321 ]]; then
    IFS= read -r shebang < "$mojo_path" || true
    read -r -a shebang_parts <<<"${shebang#\#!}"
    interpreter_command="${shebang_parts[0]:-}"
    if [[ "${interpreter_command##*/}" == env ]]; then
        case "${shebang_parts[1]:-}" in
            -S) interpreter_command="${shebang_parts[2]:-}" ;;
            -*) echo "Unsupported Mojo launcher env shebang: $shebang" >&2; exit 1 ;;
            *) interpreter_command="${shebang_parts[1]:-}" ;;
        esac
    fi
    interpreter_path="$(command -v "$interpreter_command" 2>/dev/null || true)"
    [[ -n "$interpreter_command" && -n "$interpreter_path" && -x "$interpreter_path" ]] || {
        echo "Cannot identify the Mojo launcher interpreter: $shebang" >&2
        exit 1
    }
    interpreter_path="$(realpath -e -- "$interpreter_path")"
fi

fingerprint="$({
    printf 'compiler=%s\nversion=%s\nflags=%s\nincludes=%s\n' \
        "$mojo_path" "$actual_version" "$mojo_flags" "$include_flags"
    printf 'platform=%s/%s\nlibc=%s\n' "$(uname -s)" "$(uname -m)" \
        "$(getconf GNU_LIBC_VERSION 2>/dev/null || true)"
    sha256sum -- "$mojo_path"
    if [[ -n "$interpreter_path" ]]; then
        printf 'interpreter=%s\n' "$interpreter_path"
        sha256sum -- "$interpreter_path"
    fi
    for package in "${mojo_packages[@]}"; do
        find "$package" -type d -name __pycache__ -prune -o -type f -print0
    done | LC_ALL=C sort -z | xargs -0 -r sha256sum --
    find src tests -type f -name '*.mojo' -print0 | \
        LC_ALL=C sort -z | xargs -0 -r sha256sum --
    sha256sum -- Makefile scripts/ci/update-unit-build-state.sh scripts/ci/build-unit-target.sh
} | sha256sum | cut -d ' ' -f1)"

mkdir -p -- "$(dirname -- "$state_path")"
if [[ -f "$state_path" ]] && [[ "$(cat -- "$state_path")" == "$fingerprint" ]]; then
    exit 0
fi

temporary_state="$(mktemp -- "${state_path}.XXXXXXXXXX")"
trap 'rm -f -- "$temporary_state"' EXIT
printf '%s\n' "$fingerprint" >"$temporary_state"
mv -f -- "$temporary_state" "$state_path"
