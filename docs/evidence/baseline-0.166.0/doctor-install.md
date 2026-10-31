# `doctor --install` evidence

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Active reference: Prodex 0.166.0 at `9f69e1835808f478f59f12a3ae3fa88027d896a4`.

Verified Linux oracle SHA-256: `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In 0.166.0, `doctor --install` selects install-only mode before `AppState` load,
then collects prerequisite rows and renders an Install Checks panel.
`tests/test_doctor_install_01660.py` compares this path with a temporary `HOME`,
empty or fixture-only `PATH`, temporary Codex paths, and non-interactive stdout.
Fake commands provide all probe output. The fake `codex` handles `--version`
and `login status`; no real Codex executable, account, credentials, provider
traffic, or login flow is used. Neither run creates `.prodex` or `.codex` state.
Both binaries run through the CI `sandbox_command` bubblewrap launcher with
user, mount, PID, and network namespaces, a cleared inherited environment, and
only the temporary fixture root, tested binary, required shared libraries, the
read-only zoneinfo database, `/bin/sh`, and `/bin/cat` mounted.

Present-command and empty-`PATH` rows match the oracle except for these safer
Modex outputs: it removes synthetic environment secrets before child execution,
redacts Authorization values found in a displayed stdout or stderr line,
redacts token-like values in displayed paths, then escapes terminal controls in
tool output and environment-derived paths. The fixture confirms child probes
retain temporary `HOME`, drop a synthetic `OPENAI_API_KEY` and arbitrary
sentinel, and never receive `PRODEX_HOME`, `PRODEX_SHARED_CODEX_HOME`, or
`PRODEX_OPTIMIZERS_HOME`. Only Codex CLI version and auth-status probes receive
the temporary `CODEX_HOME`; the other fake commands confirm it is absent.

The fixture combines token-like values with terminal controls in two displayed
paths. For those transformed rows, the baseline panel lays out the original
values before the test sanitizes its captured bytes, while Modex sanitizes the
values before panel layout. Redaction removes the control suffix after the
token, so the rendered rows can differ in bytes and wrapping. The test asserts
redaction and absence of raw controls, then compares all unaffected rows. This
case records that specific output difference; it does not establish parity for
arbitrary long paths.

The wrapper fixture records a reference edge case: the release's Codex path
resolver skips a Prodex wrapper, then falls back to the bare `codex` command.
`doctor --install` consequently executes that PATH wrapper for both version and
auth-status checks. Modex instead reports that no safe external Codex CLI is
available and runs neither probe.

The pinned install helpers format every `command_probe_output` error as
`missing (...)`, including timeout and output-cap errors. `capture_with_env`
uses the same 15-second and 1 MiB limits and classification; the output-cap
fixture verifies the oracle result. It kills and reaps the direct child on
timeout. The pinned stdlib has no process-group spawn support, so timeout
cleanup does not guarantee termination of descendants that inherit a probe's
output descriptors.

Interactive rendering is not implemented: Prodex uses a terminal UI, while
Modex prints a plain panel. Modex honors `PRODEX_TERM_COLUMNS`; otherwise it
uses 120 columns.

The fixture also confirms that Modex detects a managed Caveman directory. It
reports that candidate as `degraded` because Caveman manifest, version, and
digest validation is not implemented. Other `doctor` operations remain guarded.

Prodex 0.166.0 accepts valid `--tail-bytes` values with `--install` in either
order and keeps the install-only panel unchanged; the argument is ignored by
that report mode. Modex supports one `--install` plus an optional validated
`--tail-bytes` value. The oracle rejects repeated `--install`, missing or
invalid tail-byte values, duplicate tail-byte options, and false-valued
`--runtime`/`--quota` flags before running probes. Modex rejects the tested
cases with matching diagnostics, including selected attached and separated
option orderings.

## Manual real-Codex offline check

On 2026-10-31, `tests/manual_doctor_codex_offline_01660.py -v` passed one test
against the pinned Linux x86-64 Prodex 0.166.0 oracle and Codex 0.166.0
executable. Modex was built from worktree commit `fe24cf1` (binary SHA-256
`093e8bf388ab34b8eed51212d7f899dd44bbdaceca610d1b8d014e8d4c1307c0`). The
oracle SHA-256 was
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`; the
Codex executable SHA-256 was
`b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8`.

The direct Codex probes returned `codex-cli 0.166.0` on stdout and `Not logged
in` on stderr with exit status 1. The real Codex CLI version and auth rows then
matched in the Prodex and Modex `doctor --install` panels, as did the remaining
panel rows after removing their intentionally different home-path rows. The
isolated Codex home contained only temporary helper scratch files; the harness
checks for auth, profile, session, history, config, and application-home state.
It also checks that neither panel exposes the synthetic API key.

The check ran with empty synthetic `HOME` and `CODEX_HOME` directories, a
private `/tmp` tmpfs, loopback only, and no IPv4 or IPv6 default route. It
invokes `doctor --install` only; it does not invoke Super, start a Codex turn,
perform account login, or contact a provider. This qualifies only the tested
Linux x86-64 offline Doctor path, not interactive rendering, other release
targets, or broader Doctor parity.

Reproduce after building Modex and obtaining the checksum-pinned oracle and
Codex executables:

```sh
MODEX_BINARY=/path/to/build/modex \
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu \
CODEX_BINARY=/path/to/codex-0.166.0/codex-x86_64-unknown-linux-musl \
timeout 120s unshare -Urnm sh -eu -c '
  mount --make-rprivate / &&
  mount -t tmpfs -o mode=1777 tmpfs /tmp &&
  ip link set lo up &&
  mkdir -m 700 /tmp/home /tmp/work /tmp/codex-home &&
  exec env -i \
    HOME=/tmp/home TMPDIR=/tmp/work CODEX_HOME=/tmp/codex-home \
    PATH=/usr/bin:/bin:/usr/sbin:/sbin \
    MODEX_BINARY="$MODEX_BINARY" PRODEX_ORACLE="$PRODEX_ORACLE" \
    CODEX_BINARY="$CODEX_BINARY" MODEX_DOCTOR_CODEX_NETNS=1 \
    PYTHONPATH=tests \
    python3 tests/manual_doctor_codex_offline_01660.py -v
'
```
