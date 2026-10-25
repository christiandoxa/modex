"""Capture actual app-server argv projection using an isolated synthetic Codex."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time

from test_cli import ORACLE, ROOT


FIXTURES = ROOT / "tests/fixtures/app-server-args"
ORACLE_SHA256 = "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a"
CASES = [
    ("model_pair", ["-m", "fixture-model"]),
    ("model_inline", ["--model=fixture-model"]),
    ("model_quote_slash", ["-m", 'quote"slash\\']),
    ("model_line_feed", ["-m", "line\nnext"]),
    ("model_controls", ["-m", "\b\t\r\f\x01\x1b\x7f"]),
    ("model_unicode", ["-m", "雪とé"]),
    ("model_empty", ["--model="]),
    ("model_backslash", ["-m", "\\"]),
    ("model_quote", ["-m", '"']),
    ("model_apostrophe", ["-m", "'"]),
    ("model_both_quotes", ["-m", "'\""]),
    ("model_apostrophe_slash", ["-m", "'\\"]),
    ("model_tab", ["-m", "a\tb"]),
    ("model_carriage_return", ["-m", "a\rb"]),
    ("model_newline", ["-m", "\n"]),
    ("model_trailing_newline", ["-m", "a\n"]),
    ("model_leading_newline", ["-m", "\na"]),
    ("model_newline_quote", ["-m", 'a\n"b']),
    ("model_newline_apostrophe", ["-m", "a\n'b"]),
    ("model_newline_backslash", ["-m", "a\n\\b"]),
    ("model_newline_three_quotes", ["-m", 'a\n"""b']),
    ("model_newline_three_apostrophes", ["-m", "a\n'''b"]),
    ("model_three_quotes", ["-m", '"""']),
    ("model_three_apostrophes", ["-m", "'''"]),
    ("model_multiline_controls", ["-m", "a\n\x01\x1b\x7f"]),
    ("model_crlf", ["-m", "a\r\nb"]),
    ("configuration_pairs", ["--config", "a=true", "--enable", "fixture", "--disable", "other", "--code-mode-host", "fixture-host", "--strict-config"]),
    ("configuration_inline", ["--config=a=true", "-c=b=false", "--enable=ignored", "--disable=ignored"]),
]
CASES += [(f"model_escape_{index:02d}", ["-m", value]) for index, value in enumerate([
    'a"b', "a'b\"c", "a'''b\"c", "a'''b\"c\\", 'a"""b\'c',
    'a"""b\'\'\'c', 'a"""b\'\'\'c\n', "a\\\tb", "a\\\rb", "a\\\x1bb",
    'a"\tb', "a'\\b\n", "a\\'''b", 'a\n"b\'c', 'a\n""b', 'a\n""""b',
    'a\n"""b\'c', "a\n\\b'c", 'a\n""', '""a\n', "a\n''", "''a\n",
    'a"\x01b', "a'\\\x01b", 'a\n"""b\\c', 'a\n"""b\'\'\'c\\d',
])]


def synthetic_codex(path):
    path.write_text("#!" + sys.executable + "\n" + textwrap.dedent('''
        import json, os, pathlib, sys
        args = sys.argv[1:]
        root = pathlib.Path(os.environ["MODEX_ARG_CAPTURE_ROOT"])
        (root / ("call-" + str(os.getpid()) + ".json")).write_text(json.dumps(args))
        if "--version" in args:
            print("codex-cli 0.153.2")
            raise SystemExit(0)
        if "app-server" in args and "--help" in args:
            print("Codex app-server")
            raise SystemExit(0)
        if "app-server" in args and "--stdio" in args:
            for line in sys.stdin:
                frame = json.loads(line)
                value = {"data": [{"hooks": []}]} if frame["method"] == "hooks/list" else {}
                print(json.dumps({"id": frame["id"], "result": value}), flush=True)
    '''), encoding="utf-8")
    path.chmod(0o700)


def capture_case(scratch, name, tail):
    root = scratch / name
    root.mkdir(mode=0o700)
    for directory in ("home", "prodex", "shared", "xdg-config", "xdg-cache"):
        (root / directory).mkdir(mode=0o700)
    cache = root / "prodex/update-check.json"
    cache.write_text(json.dumps({"source": "GitHub", "latest_version": "0.439.1", "checked_at": int(time.time())}), encoding="utf-8")
    cache.chmod(0o600)
    child = root / "codex"
    synthetic_codex(child)
    environment = {
        "HOME": str(root / "home"), "PRODEX_HOME": str(root / "prodex"),
        "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
        "XDG_CONFIG_HOME": str(root / "xdg-config"), "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "TMPDIR": str(root), "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PRODEX_CODEX_BIN": str(child),
        "MODEX_ARG_CAPTURE_ROOT": str(root),
    }
    command = [str(ORACLE), "super", "--provider", "deepseek", "--api-key", "synthetic-provider-key", "--base-url", "http://127.0.0.1:1/v1", "--skip-quota-check", "--no-presidio", "--model", "deepseek-chat", "exec", "--", *tail]
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True, timeout=20, check=False)
    calls = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.glob("call-*.json"))]
    preflight = [args for args in calls if args[-2:] == ["app-server", "--stdio"]]
    runtime = [args for args in calls if "exec" in args]
    if result.returncode or len(preflight) != 1 or len(runtime) != 1:
        raise RuntimeError(f"{name}: expected one successful preflight and launch: exit={result.returncode}, calls={calls}, stderr={result.stderr!r}")
    return {"name": name, "tail": tail, "returncode": result.returncode, "runtime_args": runtime[0], "app_server_args": preflight[0][:-2]}


def main():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("pinned oracle checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="modex-app-server-args-") as directory:
        cases = [capture_case(Path(directory), name, tail) for name, tail in CASES]
    FIXTURES.mkdir(parents=True, exist_ok=True)
    catalog = {"baseline_commit": "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3", "oracle_sha256": ORACLE_SHA256, "capture_harness": "tests/capture_app_server_args.py", "scope": "Actual runtime argv and hook-preflight argv from successful isolated Super launches with a synthetic Codex. No provider request is made. Captured synthetic paths remain literal strings; no output normalization is applied.", "cases": cases}
    (FIXTURES / "cases.json").write_text(json.dumps(catalog, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"captured {len(cases)} app-server argv cases")


if __name__ == "__main__":
    main()
