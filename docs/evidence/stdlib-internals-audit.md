# Mojo 1.2.0 stdlib source audit

Inspected the pinned Mojo 1.2.0 (2016d0cd) standard-library source under
`/home/doxa/.cache/modex/toolchains/mojo-1.2.0-source/std`. These are API gaps
in this toolchain version, not claims about future Mojo releases.

The 0.439.1 checkpoint proved a narrower startup-only alternative to missing
spawn file actions: `process_spawn.mojo` temporarily swaps parent stdio using
the bundled `dup`/`dup2` wrappers, spawns with an explicit environment, then
restores descriptors and flags. This requires no concurrent parent I/O and
does not provide general thread-safe spawning. Timed direct-child poll/kill/
wait and bounded nonblocking hook RPC reads are now tested. Process groups,
descendant cleanup, durable storage and permission repair remain gaps.
Current evidence: `docs/evidence/checkpoint-04391-tests.txt`.

An additional deterministic closed-stdin probe then exposed fatal SIGPIPE on
the pipe request writer. The official `std/net/_sys/unix.mojo` already exposes
`socketpair` and `send` with `MSG_NOSIGNAL`; Modex now uses these wrappers for
hook request writes, without new bindings or global signal changes. The live
closed-stdin regression and production launch cleanup tests pass. The before/fix status is in
`docs/evidence/app-server-closed-stdin-regression.json`.

The remaining paragraphs preserve the earlier audit's findings before those
new startup-only checks; their redirection/deadline limitations are historical.

## Filesystem and process APIs

- `std/os/os.mojo` and `std/os/__init__.mojo` expose no chmod/fchmod, fsync,
  flock, or rename/replace wrapper. `std/io/file.mojo` opens files with mode
  `0o666` and writes through `write(2)`; it exposes no durable sync operation.
- `std/os/process.mojo`: `Process.run(path, argv)` passes the parent's
  environment from `_get_environ()` to `posix_spawnp`. The pinned
  `std/sys/_libc.mojo` wrapper passes null spawn attributes and file actions;
  `Process.run` has no separate environment or stdio-redirection arguments.
- The existing internal `posix_spawnp` wrapper does accept an explicit `envp`.
  `src/modex/process_spawn.mojo` now uses it with an absolute executable path,
  stable owned argv/environment strings and the official `Process` owner.
  Native checks verify long/empty/Unicode arguments, environment replacement,
  an omitted parent sentinel, unchanged parent environment, invalid inputs and
  exit status. The standalone parent and synthetic Mojo child also run in an
  isolated filesystem with only platform/official Mojo runtime libraries.
  Evidence: `docs/evidence/inspection-policy-tests.txt`. This closes the limited
  explicit-environment capability gap; it does not provide redirected I/O,
  deadlines, process groups or descendant cleanup.
- The same bundled module supplies `dup`/`dup2`. Temporarily redirecting the
  parent's descriptors would affect concurrent parent I/O; no such global
  redirection is included in Modex. Spawn file-actions remain unavailable.
- `std/os/process.mojo` provides `Pipe` read/write, `ProcessStatus`, direct-child
  `kill`/`interrupt`/`hangup`, `poll`, and `wait`. `probes/process.mojo` was
  previously compiled and run successfully for pipe bytes, direct argv spawn,
  exit status, and direct-child kill/wait. It does not establish process-group
  cleanup, descendant cancellation, custom child environments, or redirection.
- `std/subprocess/subprocess.mojo` has `run(cmd)`, implemented with shell
  `popen` and stdout capture. A limited synthetic probe passed:

  ```text
  mkdir -p build/probes
  mojo build -O3 --target-cpu=x86-64-v3 probes/stdout_capture.mojo -o build/probes/stdout_capture
  build/probes/stdout_capture
  official stdout capture: PASS
  ```

  The retained source is `probes/stdout_capture.mojo`. This proves only stdout
  capture for the probe. The shell-command API is not
  used by Modex and does not satisfy its product restriction on subprocess
  helpers.

## Terminal and file-lock limits

- `std/os/os.mojo` exposes `isatty`, but the source contains no terminal raw
  mode, PTY creation, or terminal-dimensions API. The only size helper found is
  `std/benchmark/_progress.mojo::_get_terminal_size`, which parses `COLUMNS`
  and `LINES` with `(80, 24)` fallback; it does not query a terminal.
- `std/sys/_libc.mojo` has an internal variadic `fcntl` wrapper, but no advisory
  file-lock API or lock-record type. A manual Linux ABI experiment under
  `test-results/file-primitives-audit/` is excluded from the product evidence:
  its hand-declared Linux `struct flock` does not establish frozen `flock`
  semantics or authorized portable locking. No ABI code is included here.

The source audit identifies missing wrappers and incomplete facilities in this
pinned stdlib. It does not establish that compliant alternatives can never be
added to a future toolchain. Runtime proof is limited to the specific positive
probes described above.
