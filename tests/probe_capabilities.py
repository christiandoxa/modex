"""Compile/run capability reproducers and retain actual diagnostic evidence."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/capabilities"
BUILD = ROOT / "build/probes"
COMPILER = shutil.which("mojo")
FLAGS = ["-O3", "--target-cpu=x86-64-v3"]


def invoke(arguments, *, environment=None):
    result = subprocess.run(arguments, cwd=ROOT, env=environment,
                            capture_output=True, timeout=60, check=False)
    return {"command": [str(arg) for arg in arguments], "exit_code": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "stderr": result.stderr.decode("utf-8", "replace")}


def main():
    if not COMPILER:
        raise SystemExit("Pinned Mojo compiler is required")
    version = invoke([COMPILER, "--version"])
    if version["exit_code"] or version["stdout"].strip() != "Mojo 1.2.0 (2016d0cd)":
        raise SystemExit("Pinned Mojo 1.2.0 (2016d0cd) is required")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    records = []
    failed = False
    for name in ("platform", "process", "socket"):
        source = f"probes/{name}.mojo"
        binary = BUILD / name
        compiled = invoke([COMPILER, "build", *FLAGS, source, "-o", binary])
        record = {"source": source, "compiler": version["stdout"].strip(), "compile": compiled}
        if compiled["exit_code"] == 0:
            with tempfile.TemporaryDirectory(prefix="modex-capability-") as directory:
                arguments = [binary]
                if name == "platform":
                    arguments.append(Path(directory) / "filesystem")
                record["run"] = invoke(arguments, environment={
                    "HOME": directory, "PATH": "", "MODEX_PROBE_SENTINEL": "isolated-probe",
                })
            record["result"] = "PASS" if record["run"]["exit_code"] == 0 else "FAIL"
        else:
            record["result"] = "FAIL"
        failed |= record["result"] == "FAIL"
        records.append(record)
        print(f"{name}: {record['result']}")
    for source in sorted((ROOT / "probes/gaps").glob("*.mojo")):
        relative = str(source.relative_to(ROOT))
        compiled = invoke([COMPILER, "build", *FLAGS, relative, "-o", BUILD / source.stem])
        missing_import = "unable to locate module" in compiled["stderr"] or (
            "does not contain" in compiled["stderr"] or "cannot be found" in compiled["stderr"]
        )
        result = "PUBLIC_API_GAP" if compiled["exit_code"] and missing_import else "REVIEW_REQUIRED"
        records.append({"source": relative, "compiler": version["stdout"].strip(),
                        "compile": compiled, "result": result})
        failed |= result == "REVIEW_REQUIRED"
        print(f"{source.stem}: {result}")
    (OUTPUT / "run.json").write_text(json.dumps({"schema_version": 1,
        "host": "x86_64-unknown-linux-gnu", "probes": records}, indent=2) + "\n")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
