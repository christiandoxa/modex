# Upstream log event selection

Both Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and
0.439.2 (`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) require the raw runtime
line to contain `upstream_payload` and the parsed event to equal that name.
The substring may appear anywhere in the line. Their upstream payload parser is
`crates/prodex-app/src/app_commands/log_upstream_payload.rs::upstream_payload_event_from_runtime_line`.

Before this change, Modex emitted an escaped `upstream\u005fpayload` event
without the literal substring in `log last`; its stream and upstream followers
also projected unrelated events that had `payload_b64`. Synthetic process
comparisons with the pinned binaries reproduce those mismatches. The shared
selection now applies both checks before decoding and redaction. An escaped
name remains accepted when another field contains the literal substring.

`tests/test_log_upstream_selection_01651_04392.py` compares checksum-pinned
release processes and Modex in JSON and plain modes for `log last`, initial
snapshots, and appended lines in both followers. Fixtures use isolated homes
and synthetic content. This covers selected Linux x86-64 file-backed log
selection; live sources, other event families, security behavior, and all six
release targets are not established by these checks.
