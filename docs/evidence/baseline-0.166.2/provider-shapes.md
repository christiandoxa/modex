# Provider request and response shapes

`tests/test_provider_shapes_01662.py` runs the existing synthetic shape corpus
against the checksum-verified Prodex 0.166.2 Linux oracle and the production
Modex executable. It covers buffered Responses request bodies, an Anthropic
mixed-tool request, streamed chat event shapes and metadata ordering, and
selected combo retry controls. Generated item IDs are normalized where the
corpus specifies; the remaining compared structures are preserved.

All nine methods passed on Linux x86-64 with synthetic credentials and
loopback-only peers. The historical fixture's update-cache version remains
synthetic and does not change the selected oracle. The active wrapper also
checks empty and non-string streamed `system_fingerprint` updates against the
release; see `provider-stream-fingerprint.md`. These cases do not establish
complete provider, lifecycle, security, or other-platform parity.
