# Generated stateless session matrix

`tests/test_session_generated_stateless_matrix.py` creates isolated synthetic
session roots and runs the real Prodex 0.165.1, frozen Prodex 0.439.2, and
Modex CLIs. The tests verify both oracle checksums before running and use the explicit
`PRODEX_ORACLE_01651` and `PRODEX_ORACLE_04392` overrides. Each target
gets its own root, home, and workspace through the existing bubblewrap helper.
The test normalizes only the fixture-root path and compares return code, stdout,
and stderr byte for byte.

The five cases cover metadata alias precedence and blank-value fallback;
last-value behavior for duplicate type, payload, metadata, timestamp, and
provider keys; record order and ID updates for missing, non-string,
`session_meta`, `turn_context`, other, and empty type values; timestamp offsets,
numeric timestamps, invalid timestamp fallback, file-time fallback, and sort
ties; and stateless query matches for ID, title, cwd, provider, and path, with
parent ID and timestamp as negative controls.

All five matrix tests passed on Linux x86-64. Every generated output matched
across both pinned releases and Modex. The production build, product dependency
audit, test census, and `git diff --check` passed. No substantial stateless
report or query mismatch appeared in this matrix.

Commands:

```text
rtk make build
rtk python3 tests/test_session_generated_stateless_matrix.py
rtk python3 scripts/ci/check-product-dependencies.py
rtk python3 scripts/ci/check-test-census.py
git diff --cached --check
```

The tests verify Prodex 0.165.1 SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and Prodex
0.439.2 SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

This does not qualify managed profile state, other release targets, security
behavior, or overall parity. All six baseline release targets remain in the
parity denominator.
