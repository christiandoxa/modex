# Provider relay routes and bodyless framing

`tests/test_provider_relay_01662.py` reuses three production process
comparisons from the relay harness and binds both sides to the checksum-pinned
Prodex 0.166.2 Linux x86-64 oracle (`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`).
It covers the `/models` and `/v1/models` catalog aliases, selected model lookup,
query and method forwarding, a custom `/tenant/api/v9` base path, synthetic
upstream error bodies, same-connection reuse after bodyless SSE 204/304
responses, and raw bodyless 204/304/205 Responses wire framing. Synthetic peers
bind only to `127.0.0.1`; credentials, provider traffic, and external network
access are not used. It also checks raw local-error wires for an unsupported
route (404), invalid request target (400), and malformed Responses request
(502).

The production upstream request writer now matches the release's
`Content-Length` behavior for empty requests: it omits the field for empty
GET, HEAD, POST, and PUT requests. The Chat Completions comparison exercises
empty GET/HEAD/POST/PUT, nonempty GET/HEAD/POST, and `HEAD /v1/models`; the
native Messages comparison exercises empty and nonempty GET/HEAD/POST/PUT.
Nonempty requests carry their exact byte length. The Chat route forwards a
synthetic bearer credential, while native Messages forwards the synthetic
`x-api-key` and no `Authorization` header. A local credential control confirms
that invalid credentials on bodyless GET/HEAD still produce 401 without
upstream dispatch.

On 2026-10-31, `make build` succeeded and all nine tests in
`test_provider_relay_01662.py` passed against Modex and the checksum-pinned
oracle. The run used synthetic loopback peers in a fresh private network
namespace with only loopback enabled and no default IPv4 or IPv6 route. This
adds Linux x86-64 evidence for the listed routes, methods, and body shapes;
other provider behavior, security behavior, platforms, and all six release
targets remain unqualified.

On 2026-10-31, the original four comparisons passed inside Bubblewrap's private
filesystem namespace, sharing a fresh outer `unshare -Urn` network namespace
with only loopback enabled and no default IPv4 or IPv6 route. Modex was built
from `1d6e659d939d42a500ac6a34f5f1f19e56bd5e1d`. The custom-path comparison
confirms that a synthetic `POST /models?trace=synthetic` forwards its body,
query, and configured bearer key to `/tenant/api/v9/models?trace=synthetic`.
The five-test relay module passed after the header-casing fix in the worktree
based on `d85850c`. All three local-error cases now match the release's exact
`Content-Type` spelling, status, remaining headers, and body, without upstream
dispatch. This is Linux x86-64 regression evidence, not complete provider-relay
parity; other routes, transport behavior, platforms, and the six-target
denominator remain unqualified.

The earlier three-comparison capture recorded Modex commit
`d69f6b332f7e187019c1972f06a9f7007e68a5ac`. Its equivalent after the Modex
history rewrite is `f7bfcaf0ac5441266225a9b7c9880c664427f918`; the two
commits have identical trees, subjects, and timestamps.

To reproduce from the repository root, export the verified active oracle and
the built Modex path, then run the existing WebSocket fallback sandbox helper
inside a fresh network namespace. The inline driver below selects this test
module while reusing the established read-only workspace/oracle mounts,
synthetic HOME/XDG directories, private `/tmp`, and Bubblewrap network-sharing
setup. It fails before testing if the namespace has another interface or a
default route.

```sh
export PRODEX_ORACLE="$(python3 scripts/ci/reference.py oracle active)"
export MODEX_BINARY="$PWD/build/modex"
unshare -Urn -- /usr/bin/python3 - <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path.cwd().resolve(strict=True)
sys.path.insert(0, str(root / "scripts/ci"))
import run_websocket_fallback_01660 as sandbox

ip = shutil.which("ip")
if not ip:
    raise SystemExit("iproute2 is required")
subprocess.run([ip, "link", "set", "lo", "up"], check=True)
links = subprocess.run([ip, "-o", "link", "show"], check=True,
                       capture_output=True, text=True).stdout.splitlines()
if len(links) != 1 or "lo" not in links[0] or "UP" not in links[0]:
    raise SystemExit(f"expected only loopback to be up: {links!r}")
for args in ([ip, "route", "show", "default"],
             [ip, "-6", "route", "show", "default"]):
    if subprocess.run(args, check=True, capture_output=True,
                      text=True).stdout.strip():
        raise SystemExit("private network namespace has a default route")

modex = Path(os.environ["MODEX_BINARY"]).resolve(strict=True)
oracle = Path(os.environ["PRODEX_ORACLE"]).resolve(strict=True)
bwrap = Path(shutil.which("bwrap")).resolve(strict=True)
environment = {
    "MODEX_REAL_CODEX_NETNS": "1",
    "MODEX_BINARY": str(modex),
    "PRODEX_ORACLE": str(oracle),
    "PRODEX_ORACLE_01660": str(oracle),
    "PYTHONPATH": os.pathsep.join((str(root / "tests"), str(root))),
}
command = sandbox.bwrap_command(
    bwrap=bwrap,
    root=root,
    command=(Path(sys.executable).resolve(strict=True),
             root / "scripts/ci/run-unittest.py",
             "test_provider_relay_01662.py"),
    environment=environment,
    bind_paths=[modex, oracle, *(path for path in sandbox.python_runtime_paths()
                                if Path(path).resolve() != sandbox.SCRATCH)],
)
command[command.index("--unshare-all")] = "--share-net"
raise SystemExit(subprocess.run(command, check=False).returncode)
PY
```
