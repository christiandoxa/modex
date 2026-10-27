#!/usr/bin/env bash
set -euo pipefail

if command -v bwrap >/dev/null 2>&1; then
    command -v bwrap
    exit 0
fi

command -v apt-get >/dev/null 2>&1 && command -v dpkg-deb >/dev/null 2>&1 || {
    echo 'bubblewrap is missing and apt-get/dpkg-deb are unavailable.' >&2
    exit 1
}

install_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/modex-ci-bubblewrap"
mkdir -p -- "$install_root/download" "$install_root/root"
if ! compgen -G "$install_root/download/bubblewrap_*.deb" >/dev/null; then
    (cd -- "$install_root/download" && apt-get download bubblewrap >&2)
fi
package="$(find "$install_root/download" -maxdepth 1 -type f -name 'bubblewrap_*.deb' -print -quit)"
[[ -n "$package" ]] || {
    echo 'apt-get download did not provide the bubblewrap package.' >&2
    exit 1
}
dpkg-deb --extract "$package" "$install_root/root"
bwrap_bin="$install_root/root/usr/bin/bwrap"
[[ -x "$bwrap_bin" ]] || {
    echo 'The downloaded Ubuntu package did not contain an executable bubblewrap.' >&2
    exit 1
}

if [[ -n "${GITHUB_PATH:-}" ]]; then
    printf '%s\n' "$(dirname -- "$bwrap_bin")" >>"$GITHUB_PATH"
fi
printf '%s\n' "$bwrap_bin"
