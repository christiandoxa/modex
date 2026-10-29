# Raw stream-payload event selection

Both Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and
0.439.2 (`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) check for the literal
`stream_payload` substring before parsing a runtime log line, in
`crates/prodex-app/src/app_commands/log_stream.rs::stream_payload_event_from_runtime_line`.
The check examines the entire raw line, not just the event field.

A synthetic JSON line with event `stream\u005fpayload` but no literal
`stream_payload` elsewhere is ignored by both release processes. Before this
change Modex decoded the event and emitted it. Modex now applies the same raw
check before projecting the event in both the initial snapshot and follow path;
its existing redaction remains in place. If another field contains the literal
substring, both releases accept the escaped event name, as does Modex.

`tests/test_log_stream_escaped_event_01651_04392.py` compares checksum-pinned
release processes and Modex for JSON and plain output. It checks rejected and
accepted escaped events in initial snapshots and appended lines, with a normal
event as a follow control. Fixtures use isolated temporary homes and synthetic
contents. The pre-change Modex binary emitted the rejected initial marker; the
updated process comparison passed. This covers selected Linux x86-64 log-stream
selection only, not live sources, other event types, or all six release targets.
