# Local relay WebSocket fallback with identical duplicate headers

`tests/test_local_relay_websocket_fallback_01662.py` compares the production
Super relay with the checksum-pinned Prodex 0.166.2 Linux x86-64 oracle
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`). The
test sends a fully captured WebSocket fallback request and an authenticated
valid follow-up on one HTTP/1.1 connection. It covers duplicate, identical
`Connection: keep-alive` fields and duplicate, identical `Upgrade: websocket`
fields. Both products return 426 and then 200, with one synthetic upstream
dispatch. Modex previously closed after the 426. It now reuses the connection
when all repeated Connection and Upgrade values match case-insensitively and
the existing request parser has captured the request with unambiguous framing.

Controls keep conflicting repeated values fail-closed in Modex: conflicting
Connection values and conflicting Upgrade values are still followed by a
connection close and no Modex upstream dispatch, while the release accepts the
follow-up. Requests without Content-Length also remain fail-closed in Modex;
the release reuses that socket and dispatches the following request. Chunked
WebSocket request bodies remain fail-closed in Modex; the release returns 426
then 400 when the unconsumed chunk bytes reach its request parser. A conflicting
duplicate Content-Length remains rejected: Modex returns 426 and closes
without dispatch; the release returns 426 followed by 400 from the unconsumed
body bytes. The change does not relax body framing, client authorization, or
connection ownership checks.

`scripts/ci/run_local_relay_websocket_fallback_01662.py` runs the comparison in
a Bubblewrap-created rootless user and network namespace with only loopback
enabled and no default IPv4 or IPv6 route. Bubblewrap also isolates PID, IPC,
UTS and other supported namespaces, mounts the workspace, binary and oracle
read-only, and provides a private tmpfs. The test
uses synthetic HOME/XDG directories, synthetic credentials, and a loopback
upstream peer. It uses no account login or provider traffic.

The original wrapper's separate `unshare -Urn` step failed to write its UID map
on hosted CI. The wrapper now uses Bubblewrap directly and retains the test's
namespace and route preflight. The revised wrapper passed locally; hosted CI
verification is pending.

On the integration worktree based at `1f80094`, `make build` passed with the
existing unused-variable warnings. The wrapped oracle comparison passed one
test in 3.721 seconds, including the reuse cases and fail-closed controls. The
22-test CI routing module, product dependency audit (74 Mojo files),
50-native/237-Python test census, and `git diff --check` also passed. This
qualifies only the listed HTTP/1.1 fallback cases on Linux x86-64; conflicting
and ambiguous framing differences remain visible, as do other targets and
broader relay security behavior.

To reproduce from the repository root:

```sh
export PRODEX_ORACLE_01662="$(python3 scripts/ci/reference.py oracle active)"
MODEX_BINARY="$PWD/build/modex" python3 scripts/ci/run_local_relay_websocket_fallback_01662.py
```
