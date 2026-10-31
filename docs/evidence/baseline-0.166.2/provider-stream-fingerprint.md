# DeepSeek streamed system fingerprint

The 0.166.2 Linux x86-64 oracle and Modex were compared through the real
DeepSeek Super relay using synthetic Chat Completions SSE and a loopback-only
upstream. The pinned provider-core source projects `system_fingerprint` only
when it is a nonempty string
(`crates/prodex-provider-core/src/translators/deepseek/stream/shaping.rs`,
`deepseek_provider_core_stream_chunk_metadata`).

On a clean Modex build from `07dc37f`, the active regression failed: Modex
included `system_fingerprint: ""` when the upstream supplied an empty string,
while the oracle omitted the field. `DeepSeekChatState.apply_metadata` now
accepts only nonempty string values. The regression covers an empty value by
itself, nonempty followed by empty (retain the nonempty value), empty followed
by nonempty (accept the later value), and numeric/array values both alone and
after a nonempty value (ignore them without clearing state).

All nine methods in `test_provider_shapes_01662.py` and the buffered metadata
method in `test_provider_metadata_01662.py` passed on 2026-10-31. The run used
the established Bubblewrap helper with a private `/tmp` tmpfs, isolated 0700
HOME/TMPDIR/XDG/state directories, read-only workspace/oracle/Modex mounts,
only loopback up, and no IPv4 or IPv6 default route. Buffered metadata cases
including an empty fingerprint still pass. The existing malformed-stream
failure control also remains unchanged. This qualifies only the selected
stream metadata values on Linux x86-64, not full provider or six-target parity.

Reproduce from the repository root with the active oracle and Modex binary:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE="$(python3 scripts/ci/reference.py oracle active)" \
python3 - <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path.cwd().resolve(strict=True)
sys.path.insert(0, str(root / "scripts/ci"))
import run_websocket_fallback_01660 as sandbox

python = Path(sys.executable).resolve(strict=True)
modex = Path(os.environ["MODEX_BINARY"]).resolve(strict=True)
oracle = Path(os.environ["PRODEX_ORACLE"]).resolve(strict=True)
bwrap = Path(shutil.which("bwrap")).resolve(strict=True)
driver = r'''import os, subprocess, sys
sys.path.insert(0, os.environ["MODEX_TESTS_DIR"])
from manual_real_codex_01660_route_comparison import require_isolated_environment
require_isolated_environment()
raise SystemExit(subprocess.run(
    [sys.executable, "scripts/ci/run-unittest.py",
     "test_provider_shapes_01662.py", "test_provider_metadata_01662.py"],
    check=False,
).returncode)
'''
environment = {
    "MODEX_REAL_CODEX_NETNS": "1",
    "MODEX_BINARY": str(modex),
    "PRODEX_ORACLE": str(oracle),
    "PRODEX_ORACLE_01662": str(oracle),
    "MODEX_TESTS_DIR": str(root / "tests"),
    "PYTHONPATH": os.pathsep.join((str(root / "tests"), str(root))),
}
command = sandbox.bwrap_command(
    bwrap=bwrap, root=root,
    command=(python, "-c", driver),
    environment=environment,
    bind_paths=[modex, oracle, bwrap, *sandbox.python_runtime_paths()],
)
raise SystemExit(subprocess.run(command, check=False).returncode)
PY
```
