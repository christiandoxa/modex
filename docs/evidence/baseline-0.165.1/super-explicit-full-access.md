# Explicit Super full access against 0.165.1

The 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and
the frozen 0.439.2 source both set Super's `full_access` to true even when the
compatibility flag is absent. The existing Modex launch already passes the
corresponding Codex bypass flag; previously it rejected an explicit
`--full-access` before starting the child.

The production guard now accepts the explicit flag. Synthetic isolated
process comparisons against the checksum-pinned 0.165.1 and 0.439.2 Linux
releases cover the flag both before and after `exec`. For each, the complete
normalized child argv, upstream request path and body match; one loopback
provider request succeeds, no synthetic key is printed, and temporary
overlays are removed. Unverified Codex configuration overrides remain
guarded. The production build, native Super parser, both release-comparison
tests and guard regression passed; the 71-file import audit and 130-module
test census passed. No real credentials or paid services were used.

This qualifies only the tested DeepSeek launch path on Linux x86-64. Other
Super startup behavior, account state, and the remaining targets are open.
