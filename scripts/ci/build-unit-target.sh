#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 7 ]]; then
    echo 'usage: build-unit-target.sh output source fingerprint-file metadata-file mojo flags includes' >&2
    exit 2
fi

output="$1"
source="$2"
fingerprint_file="$3"
metadata="$4"
mojo_command="$5"
mojo_flags="$6"
include_flags="$7"

[[ -f "$fingerprint_file" && ! -L "$fingerprint_file" ]] || {
    echo "Unit input fingerprint is missing or invalid: $fingerprint_file" >&2
    exit 1
}
fingerprint="$(<"$fingerprint_file")"
[[ "$fingerprint" =~ ^[0-9a-f]{64}$ ]] || {
    echo "Unit input fingerprint has invalid content: $fingerprint_file" >&2
    exit 1
}

if [[ -d "$output" ]]; then
    echo "Refusing to replace a directory with a unit executable: $output" >&2
    exit 1
fi

if [[ -f "$output" && ! -L "$output" && -x "$output" && -f "$metadata" && ! -L "$metadata" ]]; then
    IFS=$'\t' read -r stored_fingerprint stored_hash stored_mode < "$metadata" || true
    current_mode="$(stat -c '%a' -- "$output")"
    current_hash="$(sha256sum < "$output" | cut -d ' ' -f1)"
    if [[ "$stored_fingerprint" == "$fingerprint" \
        && "$stored_hash" =~ ^[0-9a-f]{64}$ \
        && "$stored_hash" == "$current_hash" \
        && "$stored_mode" == "$current_mode" ]]; then
        exit 0
    fi
fi

mojo_path="$(command -v "$mojo_command" 2>/dev/null || true)"
[[ -n "$mojo_path" && -x "$mojo_path" ]] || {
    echo "Mojo compiler is not executable: $mojo_command" >&2
    exit 1
}

mkdir -p -- "$(dirname -- "$output")" "$(dirname -- "$metadata")"
temporary_output="$output.tmp.$$"
temporary_metadata=""
cleanup_unit_temporary_files() {
    rm -f -- "$temporary_output"
    if [[ -n "$temporary_metadata" ]]; then
        rm -f -- "$temporary_metadata"
    fi
}
trap cleanup_unit_temporary_files EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

"$mojo_path" build $mojo_flags $include_flags "$source" -o "$temporary_output"
[[ -f "$temporary_output" && ! -L "$temporary_output" && -x "$temporary_output" ]] || {
    echo "Mojo compiler did not produce an executable unit target: $temporary_output" >&2
    exit 1
}
mv -f -- "$temporary_output" "$output"

output_hash="$(sha256sum < "$output" | cut -d ' ' -f1)"
output_mode="$(stat -c '%a' -- "$output")"
temporary_metadata="$(mktemp -- "${metadata}.XXXXXXXXXX")"
printf '%s\t%s\t%s\n' "$fingerprint" "$output_hash" "$output_mode" >"$temporary_metadata"
mv -f -- "$temporary_metadata" "$metadata"
temporary_metadata=""
