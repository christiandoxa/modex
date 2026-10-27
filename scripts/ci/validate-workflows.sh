#!/usr/bin/env bash
set -euo pipefail

VERSION=1.7.12
SHA256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
TOOLS_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/modex-ci-tools/actionlint-$VERSION"
ARCHIVE="$TOOLS_DIR/actionlint.tar.gz"
mkdir -p -- "$TOOLS_DIR"
curl --fail --location --silent --show-error --retry 2 \
    "https://github.com/rhysd/actionlint/releases/download/v$VERSION/actionlint_${VERSION}_linux_amd64.tar.gz" \
    --output "$ARCHIVE"
printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum --check --status || {
    echo "actionlint $VERSION archive checksum mismatch" >&2
    exit 1
}
tar --extract --gzip --file "$ARCHIVE" --directory "$TOOLS_DIR" --no-same-owner actionlint
"$TOOLS_DIR/actionlint" -color .github/workflows/*.yml
python3 scripts/ci/check-workflow-policy.py
echo "GitHub Actions workflows validated with actionlint $VERSION (SHA-256 $SHA256)."
