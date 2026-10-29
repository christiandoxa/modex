# Super no-proxy with a loopback provider

The pinned 0.165.1 source passes `--no-proxy` into the upstream HTTP client.
Modex's guarded DeepSeek transport supports numeric loopback HTTP and connects
directly; it previously rejected the explicit option before launch.

The production guard now accepts `--no-proxy` for that existing path. Real
process comparisons against checksum-pinned 0.165.1 and 0.439.2 binaries cover
the flag before and after `exec`, with HTTP, HTTPS and ALL proxy settings pointing
to a synthetic unreachable loopback endpoint. Each process launches the
synthetic Codex child, makes one direct loopback provider request, and has the
same normalized child arguments, upstream path and request body. No synthetic
key appears in output and temporary overlays are removed. Unverified Codex
overrides remain guarded. The production build, three focused process tests,
71-file dependency audit and 130-module test census passed.

These checks do not establish public TLS, DNS, proxy, account or cross-platform
behavior. No real credentials or paid traffic were used.
