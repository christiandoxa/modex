# Existing app-root permission repair on Prodex 0.166.2

The checksum-pinned Linux x86-64 reference is Prodex 0.166.2, SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

`tests/test_secure_app_root_permissions_01662.py` starts each binary in a
private bubblewrap sandbox with a synthetic HOME, a user-owned `.prodex`
directory at mode `0755`, and one marker file. It runs only `log last --json`;
the sandbox has no network, credential, account, or provider access.

Prodex exits 0 with empty output, changes the existing directory mode to
`0700`, and preserves the marker and directory contents. Modex fails closed
with `secure application-directory permission repair is not implemented`,
leaving mode `0755` and preserving the marker. This is a reproducible current
release mismatch, not a parity pass.

The pinned Mojo 1.2.0 toolchain cannot perform the required repair through its
official standard library: compiling `from std.os import chmod` reports that
`std.os` has no `chmod`, and `Path.chmod` is unavailable. A native binding or
external helper would violate the project rules. Relaxing the ownership/mode
guard would permit log, session, or profile operations while private state is
group/world-readable, so the fail-closed behavior remains in place. No
production change is claimed.

Verified on 2026-10-31 with:

```sh
PRODEX_ORACLE=/path/to/verified/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_secure_app_root_permissions_01662.py
```

The focused test passes by asserting both release behaviors and the preserved
marker. It covers one Linux x86-64 invocation and does not qualify permission
repair on the other five release targets.
