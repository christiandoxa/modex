# Codex 0.166.0 isolated 401 comparison

## Current comparison

The same two focused cases passed in 21.029 seconds using the Modex production
sources at `c7cb160eacbd95e1d47f4b2cee74d7bc86d4f127` (unchanged from the
preceding production build) and executable SHA-256
`544d60124512ecd60efe01c1b683ead31b28a0cc6cf40402ce150cb5a7e7a9f0`.
The pinned real Codex and Prodex binaries ran with synthetic credentials in a
private user, mount, and loopback-only network namespace. In the synthetic 401
case both launchers made six requests to `/anthropic/v1/messages`; their
normalized request bodies matched, while raw bodies differed. Prodex removed
the overlay and Modex retained it, including synthetic `auth.json`. This rerun
does not qualify profile-backed routing, overlay lifecycle, or full parity.

After the active catalog and Anthropic namespace fixes, the Linux x86-64 build
from production sources at `2163ce9245513a73f5d30b6ff60bc757f714acb5` has
SHA-256 `eb64b60bbad9116ccf55ef9d0a8a3d1bc3bae59e0c2f6fe42850bcad506bcb5a`.
In an isolated user, mount and network namespace with private temporary
storage, synthetic credentials and loopback only, the real Codex 0.166.0
success case and synthetic 401 comparison passed. Both launchers routed the
401 case to `/anthropic/v1/messages` with matching normalized Codex arguments.
An earlier repeat exposed a host tool directory through `PATH`; optional-tool
discovery changed the first message and tool count. That observation is not a
controlled comparison. The harness now exposes only the requested Node binary
from that directory. With this isolation, both products made six 401 attempts
and their parsed request bodies matched after replacing temporary launch and
overlay paths and loopback ports. The raw bodies differ, and the test reports
both results without recording their contents. Behavior with additional
optional tools remains unqualified. The release removed its temporary overlay, while
Modex retained Codex-created state including `auth.json`. The test preserves
that distinction; neither request-body nor lifecycle parity is established.
An initial rerun used the older chat-response fixture and failed; the fixture
was updated to send Anthropic events for the observed route before these checks.

## Pinned artifacts

- Codex `rust-v0.166.0` Linux x86-64 musl archive SHA-256:
  `a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978`.
- Extracted Codex executable SHA-256:
  `b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8`.
- Verified Codex binary used in the comparison: the extracted release payload's
  `codex-x86_64-unknown-linux-musl` executable.
- Prodex 0.166.0 oracle executable SHA-256:
  `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.
- Modex candidate source commit: `c425701cfdb27d1b3e815011c893d5244e423d56`.
  Candidate executable SHA-256: `02795718e0788d8f59b6bcb6ae8f7a41ad4dbc6a33d493852e5256d735e06512`.
- Integrated rerun used production sources matching
  `53dd0a042f2a526516f2b72955c94f2d96aab1bf`, with executable SHA-256
  `d76e89f50deb0dfa085c10d0976592f374c7543f017221bee0e25c05412ad922`.

`tests/manual_real_codex_01660_route_comparison.py` verifies both executable
hashes and versions, then launches real Codex through the local fixtures. Its
preflight fails before any Codex or oracle process unless the rootless user
namespace marker and mapping are present, `/tmp` is a user-owned tmpfs with
private propagation, `HOME` and `TMPDIR` are directories inside it, the only
interface is an already-up loopback, and IPv4/IPv6 have no default route.
`HOME` and `TMPDIR` must be owned by the current user with mode `0700`. The run
uses synthetic provider credentials and isolated config/storage. Neither
login nor external provider traffic occurs.

## Earlier observed route and retained-state mismatch

| Launcher | Upstream path | Codex exit | `auth.json` during exit | Overlay after exit |
| --- | --- | ---: | --- | --- |
| Prodex 0.166.0 oracle | `/anthropic/v1/messages` | 1 | Unchanged | Removed; no entries remained |
| Modex candidate | `/v1/chat/completions` | 1 | Unchanged | Retained `auth.json`, `config.toml`, catalog, session state, SQLite databases, and SQLite WAL/SHM files |

Both launchers passed the same normalized Codex arguments. Both returned the
synthetic upstream 401 text without printing either synthetic key. The captured
upstream paths differ. The earlier comparison's request-count/path assertions
failed; this characterization records distinct observed paths and does not set
an expected attempt count. It does not infer why routing differs. It also does
not delete or alter either overlay's state.

An attempted raw request capture saw a Codex `POST /v1/responses` with a
43,284-byte `Content-Length`, split across `writev` iovecs. The decoder did not
recover a complete JSON body, so the tool list and route-selection cause remain
unverified. The failed capture is not evidence that a specific tool triggered
the route.

## Reproduce

The namespace replaces `/tmp` with a private tmpfs. Set `CODEX_ARTIFACT_DIR` to
the extracted payload directory, `PRODEX_ORACLE` to the verified release
binary, `NODE_BIN` to the Node binary directory, and `HOST_TOOLS_BIN` to a
directory containing Python 3.14. If the artifact directory is under host
`/tmp`, bind it before mounting tmpfs, as below.

```sh
CODEX_ARTIFACT_DIR=/path/to/extracted/codex-payload
HOST_TOOLS_BIN=/path/to/host-tools/bin
NODE_BIN=/path/to/node/bin
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu
export CODEX_ARTIFACT_DIR HOST_TOOLS_BIN NODE_BIN PRODEX_ORACLE

timeout 180s unshare -Urnm sh -c '
  mount --make-rprivate / &&
  mount --bind "$PWD" /mnt &&
  mount --bind "$CODEX_ARTIFACT_DIR" /opt &&
  mount -t tmpfs -o mode=1777 tmpfs /tmp &&
  ip link set lo up &&
  mkdir -m 700 /tmp/home /tmp/work &&
  cd /mnt &&
  exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
    PATH="$HOST_TOOLS_BIN:/usr/local/bin:/usr/bin:/bin" \
    LANG=C.UTF-8 TERM=dumb NO_COLOR=1 \
    MODEX_BINARY=/mnt/build/modex \
    CODEX_BINARY=/opt/codex-x86_64-unknown-linux-musl \
    NODE_BIN="$NODE_BIN" \
    PRODEX_ORACLE="$PRODEX_ORACLE" \
    MODEX_REAL_CODEX_NETNS=1 PYTHONPATH=tests \
    python3 tests/manual_real_codex_01660_route_comparison.py -v
'
```

The test command must run only after the wrapper has mounted the private tmpfs,
created `/tmp/home` and `/tmp/work`, and brought loopback up. It verifies that
state before launching any Codex or oracle process. The focused run passed the
Modex-only synthetic success case and the oracle/Modex 401 comparison. This is
one Linux x86-64 Codex 0.166.0 characterization; other release targets and
general routing parity remain unverified.
The same two cases passed again against the integrated build in 25.538 seconds.

## Historical Modex-only success observation

The original real-client success check used Modex build
`94b514c2fe3992a9f2219b035746820f8fe17161` with the same verified Codex 0.166.0
executable. It ran under `unshare -Urn` with only loopback enabled and no IPv4
or IPv6 default route. The one synthetic provider request went to
`/v1/chat/completions`; the check verified the per-launch local token, provider
authorization, and absence of either key in output. It made no login or paid
provider request, and did not change the installed Codex.

Reproduce the original Modex-only check with the preserved
`tests/manual_real_codex_local_auth.py`:

```sh
timeout 120s unshare -Urn env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  MODEX_BINARY=/absolute/path/to/modex CODEX_BINARY=/absolute/path/to/codex \
  NODE_BIN=/absolute/path/to/node/bin MODEX_REAL_CODEX_NETNS=1 \
  PYTHONPATH=tests python3 tests/manual_real_codex_local_auth.py -v
```

Set `MODEX_EXPECTED_CODEX_VERSION=0.165.0` only when running that historical
client check. This original command predates the stricter private-tmpfs
preflight used by the new pinned route comparison above.
