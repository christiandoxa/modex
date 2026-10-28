# Anthropic stream stop fields against 0.165.1

The pinned source reader takes `stop_reason` only when it is a string and does
not use `stop_sequence`. Before this change, Modex rejected a missing or
non-string reason and a non-string sequence. The production stream parser now
accepts those cases with the observed release mapping.

`tests/test_provider_stream_01651_characterization.py` compares complete
normalized events, the synthetic upstream request, status and cleanup through
real Super dispatch for eight cases: normal end turn, tool use, token limit,
null, missing or non-string reason, non-string sequence, and no message delta.
The checksum-verified 0.165.1 binary and Modex matched on Linux x86-64. The
native reader unit covers these cases as well. The separately pinned 0.439.2
regression remains historical.

This is limited to the tested single-search stream shape. Other event orders,
metadata and error conditions, WebSockets, and non-Linux targets remain
unverified; no provider contract is promoted to PASS.

The release also ignores unknown Anthropic event types. A synthetic future event
previously failed Modex; both production processes now complete the same tested
stream. Known malformed events remain subject to validation.
