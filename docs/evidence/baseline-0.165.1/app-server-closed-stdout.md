# App-server closed-stdout error

The verified 0.165.1 Linux oracle has SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
When a synthetic Codex app-server closes stdout after receiving `initialize`,
the oracle reports `Error: Codex hook-trust preflight initialize failed:
channel is empty and sending half is closed`.

Production Modex now reports the same final error line. The synthetic peer
records exactly one `initialize` request; both processes exit 1, write no
stdout, make no upstream request, and remove all temporary overlays. The
comparison is in `python3 tests/test_app_server_rpc_01651.py`.

As a historical control, the checksum-pinned 0.439.2 Linux oracle
(`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`)
reports the same line for this synthetic case and also sends only
`initialize`. This historical observation does not extend the 0.165.1 target
or platform claim.

The changed reader branch applies only when EOF arrives with no buffered line
bytes. A partial line at EOF is still returned to the JSON-RPC parser. The
native reader regression covers that path, while existing checks retain
separate timeout, oversized-line, closed-stdin, and malformed-frame behavior.
No real credentials or external provider traffic are used. This qualifies
closed stdout only on Linux x86-64; other targets and broader transport
behavior remain unverified.
