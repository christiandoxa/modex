"""Unapproved safe differences from the frozen Prodex 0.439.0 baseline."""

import json


def snapshot_stdout(text):
    return (
        '{"timestamp":"2026-10-24 01:02:04.000 +00:00","source":"user","text":'
        + json.dumps(text, ensure_ascii=False, separators=(",", ":"))
        + "}\n"
    ).encode()


UNAPPROVED_SAFE_DIFFERENCE = (
    {
        "input": 'api_key\u00a0=\u00a0"synthetic-secret-value"',
        "secret": "synthetic-secret-value",
        "baseline_leaks_secret": True,
        "baseline_stdout": snapshot_stdout(
            'api_key\u00a0=\u00a0"synthetic-secret-value"'
        ),
        "modex_stdout": snapshot_stdout(
            'api_key\u00a0=\u00a0"<redacted>"'
        ),
    },
    {
        "input": 'api_key=\u00a0"synthetic-secret-value"',
        "secret": "synthetic-secret-value",
        "baseline_leaks_secret": True,
        "baseline_stdout": snapshot_stdout(
            'api_key=<redacted>"synthetic-secret-value"'
        ),
        "modex_stdout": snapshot_stdout(
            'api_key=\u00a0"<redacted>"'
        ),
    },
    {
        "input": 'password=\u2003"synthetic-secret-value"',
        "secret": "synthetic-secret-value",
        "baseline_leaks_secret": True,
        "baseline_stdout": snapshot_stdout(
            'password=<redacted>"synthetic-secret-value"'
        ),
        "modex_stdout": snapshot_stdout(
            'password=\u2003"<redacted>"'
        ),
    },
    {
        "input": "password=\u2003synthetic-secret-value",
        "secret": "synthetic-secret-value",
        "baseline_leaks_secret": False,
        "baseline_stdout": snapshot_stdout("password=<redacted>"),
        "modex_stdout": snapshot_stdout("password=\u2003<redacted>"),
    },
)
