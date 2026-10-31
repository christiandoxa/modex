# Prodex 0.166.2 session-root resume prototype

## Reference and observed behavior

The comparison used the checksum-verified Prodex 0.166.2 Linux x86-64 release
(source commit `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`, binary SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`). For a
parent-owned native V2 worker, Prodex reports the owning root session before
reaching the synthetic no-profile guard. It preserves the requested target for
root and V1 sessions. Missing, cyclic, ambiguous, and conflicting ancestry
fails closed.

## Prototype results

An isolated real-process differential used synthetic session files, synthetic
home/config roots, network isolation, no credentials, and no Codex executable.
The fixture snapshots remained unchanged in every case.

- For a V2 worker whose files were under the normal session directories, the
  prototype selected and reported the same root ID as Prodex.
- Root and V1 cases kept their direct target. The Modex process then stopped at
  its existing Super startup guard; no launch parity is established.
- Missing parent metadata, cycles, conflicting parent aliases, conflicting
  root hints, and duplicate root files produced the same fail-closed diagnostics
  as Prodex.
- For a worker discoverable only through `state_*.sqlite`, Prodex selected the
  root. The prototype did not resolve the indexed file and stopped at the
  existing startup guard. SQLite lookup remains unsupported.
- A native assertion confirmed that the argument replacement helper changes
  both `--resume <worker>` and `--resume=<worker>` to the selected root ID. The
  actual child Codex argv was not observed because the launch guard prevents
  spawning a child.

The production build, focused native argument test, and synthetic differential
passed on the prototype before the later scan-cap experiment. The current
prototype source includes that unbuilt experiment, so the latest source state
has not been verified.

## Review findings

Do not integrate this prototype. Root-level parent metadata fallback is missing
when a payload object exists, and the candidate filter searches the full path
instead of only the filename stem. Exact ID normalization needs further review.
The state database path is omitted, so absence from the scanned directories is
not proof that no indexed candidate or conflict exists. The directory-entry
cap is checked after `listdir` allocates its result, and path-based directory
inspection can race with replacement. The per-record 64 MiB input limit does
not bound JSON parser node allocations or aggregate work across a long parent
chain. The prototype also rejects a symlinked session root where the reference
follows one; compatibility and safe traversal need to be resolved together.
The selected ID was observed in the
prototype status line and the argument helper was unit-checked, but spawned
argv and managed launch behavior remain unverified.

In the pinned Mojo 1.2.0 standard library, `std.os.listdir` returns a complete
list and its Linux implementation collects entries before returning. The
available path-based file and stat APIs do not provide the descriptor-relative
directory traversal needed to anchor this scan. A new native binding is outside
the project constraints; no bounded, race-safe replacement has been verified.
