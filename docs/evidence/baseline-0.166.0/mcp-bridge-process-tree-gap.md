# MCP JSONL bridge process-tree cleanup gap

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

## Reference behavior

Prodex 0.166.0 (`9f69e1835808f478f59f12a3ae3fa88027d896a4`) registers the hidden
`__mcp-jsonl-bridge` command and runs the supplied MCP server with piped stdin,
stdout, and stderr. Its bridge implementation starts the server in a separate
process group and terminates that process tree on input completion, pump errors,
or child exit. The bridge also converts incoming Content-Length or JSONL
messages to JSONL for the child, emits child messages using the most recently
observed input framing (Content-Length by default), bounds messages at 64 MiB,
framing metadata at 64 KiB, and retained stderr at 64 KiB.

## Mojo 1.2.0 limitation

The pinned Mojo 1.2.0 standard-library `posix_spawnp` wrapper passes null
file-action and spawn-attribute pointers; its source marks both APIs as not yet
implemented. `std.os.process.Process` stores and signals only the direct child
PID. The available Modex stdio-spawn helper uses that process API, so it cannot
place the child in a new process group or terminate its descendants. The
standard library also exposes no process-group creation/termination API.

A nonblocking pump could preserve message framing and byte limits, but it would
not preserve the bridge's process-tree cleanup. If an MCP server starts a
descendant that inherits stdout or stderr and then exits, that descendant can
survive while keeping the pipes open. Launching the arbitrary command with only
direct-child cleanup would therefore weaken upstream lifecycle behavior.

## Synthetic characterization

A local shell command was run inside a private Bubblewrap sandbox with all
namespaces isolated and a fresh synthetic HOME. The command started a local
`sleep` descendant and exited successfully. The descendant kept its inherited
stdout pipe open after the parent exited; terminating the process group closed
the pipe. The characterization used no Prodex or Modex command, credentials,
or network access. It demonstrates the cleanup distinction only; it is not an
oracle comparison or bridge parity test.

## Scope

The Modex baseline handles bridge help forms but leaves ordinary
`__mcp-jsonl-bridge COMMAND ...` invocations on its generic unimplemented-command
path, so no child is launched. Keep that guard until the supported toolchain
provides process-group spawn and cleanup APIs, or the project constraints
explicitly change. Framing, bounded IO, exit handling, and oracle parity remain
unimplemented and unverified here.
