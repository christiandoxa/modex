#!/usr/bin/env python3
"""Reject non-standard or non-project imports in production Mojo sources."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_.][A-Za-z0-9_.]*)")
ALLOWED_ROOTS = {"std", "modex", ""}


def main() -> int:
    failures = []
    sources = sorted((ROOT / "src").rglob("*.mojo"))
    if not sources:
        print("no production Mojo sources found", file=sys.stderr)
        return 1
    for source in sources:
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            match = IMPORT.match(line)
            if match and match.group(1).split(".", 1)[0] not in ALLOWED_ROOTS:
                failures.append(f"{source.relative_to(ROOT)}:{line_number}: {line.strip()}")
    if failures:
        print("unsupported production imports found:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Production import audit passed: {len(sources)} Mojo files use only std/internal imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
