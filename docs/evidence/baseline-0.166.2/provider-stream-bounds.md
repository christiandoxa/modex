# Provider SSE stream bounds

`tests/test_provider_shapes_01662.py` exercises the production DeepSeek Super
path against the checksum-verified Prodex 0.166.2 Linux x86-64 binary
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`). The
synthetic Codex child and upstream peer run from fresh temporary homes and
configuration; all provider traffic targets the peer on `127.0.0.1`.

The earlier handoff statement that translated SSE had a total 4 MiB response
cap was stale. `DeepSeekExchange` opens the response with
`allow_unbounded_body=True` and consumes `LoopbackHTTPStream.read_chunk()`
incrementally. Each receive uses an 8,192-byte buffer. Raw input is framed with
4 MiB per-line and per-event limits, and JSON accumulation has its own 4 MiB
limit. The large-total-body case consists of 65 bounded comment frames followed
by a small successful finish event, so it verifies that the relay does not
retain or reject the raw response by aggregate size. This is an input-framing
bound, not a constant-memory claim for translated output or conversation state.

The active-release process comparison passed on 2026-10-31:

- A 4,260,101-byte chunked SSE response completed with HTTP 200 and matching
  `response.created` / `response.completed` events.
- A line of exactly 4,194,304 bytes and a data event of exactly 4,194,304
  accounted bytes completed on both binaries. One byte over either limit
  produced matching HTTP 200 `response.failed` events with the corresponding
  `provider SSE line exceeded safe size limit (4194304)` or
  `provider SSE event exceeded safe size limit (4194304)` message.
- The malformed-stream control remains visible: the frozen oracle leaves the
  downstream stream open for a non-object chat chunk, while Modex emits a
  terminal `response.failed`; missing-choice and invalid-JSON controls match.
  This known difference is not counted as parity.

These cases qualify only the selected Linux x86-64 route and inputs. Provider
behavior on the other five release targets and complete provider parity remain
open.

Reproduce after building Modex:

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
             "test_provider_shapes_01662.py"),
    environment=environment,
    bind_paths=[modex, oracle, *(path for path in sandbox.python_runtime_paths()
                                if Path(path).resolve() != sandbox.SCRATCH)],
)
command[command.index("--unshare-all")] = "--share-net"
raise SystemExit(subprocess.run(command, check=False).returncode)
PY
```
