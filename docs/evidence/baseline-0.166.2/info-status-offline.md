# Clean-home info and status behavior

The active reference is Prodex 0.166.2 at source commit
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. The isolated Linux x86-64
oracle has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

`tests/test_info_status_offline_01662.py` compares `info --json` and
`status --once` against that oracle using a fresh synthetic HOME, no config or
credentials, empty PATH, and a Bubblewrap network namespace. Help controls
match their pinned fixtures and leave the synthetic root untouched.

On the clean home, `info --json` exits successfully and reports zero profiles,
no provider routes, the file secret backend, runtime defaults, process counts,
and recent-load/log status. It creates `.prodex/update-check.lock`. Modex
retains its unsupported-command guard and makes no filesystem changes. The
oracle's output includes live process and runtime observations as well as
runtime settings, so a hardcoded default report would be misleading.

With no profiles, `status --once` panics in the oracle's runway renderer and
exits 101. Its required observed effects include `.prodex/`,
`profile-lifecycle.json.lock`, `runtime-housekeeping.lock`, and
`update-check.lock`. `runtime-housekeeping.last-run` may also appear
asynchronously. The test asserts only the minimum required effects, not a
complete filesystem inventory. Modex returns its existing unsupported-command
error without those effects. The oracle crash is recorded as an observed
defect; it is not behavior to reproduce.

This is characterization, not Info/Status parity. No production handler was
added because the clean-home Info output depends on live dashboard inputs and
the empty-pool Status reference crashes. The check does not cover `info
--tokens`, configured profiles, or status with a profile. It uses no account
login, real credentials, provider traffic, or external network access and
qualifies Linux x86-64 only.

Verified on 2026-10-31 with:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE=/path/to/verified/prodex-0.166.2 \
python3 scripts/ci/run-unittest.py test_info_status_offline_01662.py
```
