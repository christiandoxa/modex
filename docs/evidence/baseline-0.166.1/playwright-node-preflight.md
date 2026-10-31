# Playwright Node.js preflight

Prodex 0.166.1 at `4951b813ca308fb0ba7148dbc6d6aeb74b93cd32` checks
the Node.js major version before probing `@playwright/mcp`, including in the
Super optional-tool plan. The source in
`crates/prodex-optional-tools/src/optional_tools.rs` obtains the first valid
version line, requires a major version of at least 18, and only then invokes
the package probe.

Modex's guarded Super dry-run previously reported Playwright as resolved
even for Node 17 or an unrecognized Node version. It now runs the bounded
Node version check first, rejects missing, old, invalid or unsuccessful
Node probes, and probes the package only for supported versions. A
checksum-pinned 0.166.1 process comparison uses synthetic executables and
isolated homes; a marker confirms whether the package was actually probed.

This covers the tested dry-run path on Linux x86-64. Ordinary optional-tool
activation and full Doctor health checks remain separate work. Node version
diagnostics retain Modex's redaction and terminal-control escaping.
