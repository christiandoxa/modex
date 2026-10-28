#!/usr/bin/env python3
"""Check the production source inventory and reject non-project imports."""

from collections import Counter
from pathlib import Path
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_.][A-Za-z0-9_.]*)")
ALLOWED_ROOTS = {"std", "modex", ""}


def source_inventory_failures(root: Path, sources: list[Path]) -> list[str]:
    manifest_path = root / "docs/dependencies.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"{manifest_path.relative_to(root)}: cannot read source inventory: {error}"]
    declared = manifest.get("production_sources") if isinstance(manifest, dict) else None
    if not isinstance(declared, list):
        return ["docs/dependencies.json: production_sources must be an array"]
    invalid = [value for value in declared if not isinstance(value, str) or not value]
    if invalid:
        return ["docs/dependencies.json: production_sources entries must be non-empty strings"]

    actual = {source.relative_to(root).as_posix() for source in sources}
    declared_set = set(declared)
    duplicates = sorted(path for path, count in Counter(declared).items() if count > 1)
    missing = sorted(actual - declared_set)
    stale = sorted(declared_set - actual)
    failures = []
    if duplicates:
        failures.append(f"duplicate production source entries: {', '.join(duplicates)}")
    if missing:
        failures.append(f"production source inventory is missing: {', '.join(missing)}")
    if stale:
        failures.append(f"production source inventory has stale paths: {', '.join(stale)}")
    return failures


def main() -> int:
    failures = []
    sources = sorted((ROOT / "src").rglob("*.mojo"))
    if not sources:
        print("no production Mojo sources found", file=sys.stderr)
        return 1
    inventory_failures = source_inventory_failures(ROOT, sources)
    for source in sources:
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            match = IMPORT.match(line)
            if match and match.group(1).split(".", 1)[0] not in ALLOWED_ROOTS:
                failures.append(f"{source.relative_to(ROOT)}:{line_number}: {line.strip()}")
    if inventory_failures:
        print("production source inventory mismatch:", file=sys.stderr)
        print("\n".join(inventory_failures), file=sys.stderr)
    if failures:
        print("unsupported production imports found:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
    if inventory_failures or failures:
        return 1
    print(f"Production import audit passed: {len(sources)} Mojo files use only std/internal imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
