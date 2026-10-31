# Provider request and response shapes

`tests/test_provider_shapes_01662.py` runs the existing synthetic shape corpus
against the checksum-verified Prodex 0.166.2 Linux oracle and the production
Modex executable. It covers buffered Responses request bodies, an Anthropic
mixed-tool request, streamed chat event shapes and metadata ordering, and
selected combo retry controls. Generated item IDs are normalized where the
corpus specifies; the remaining compared structures are preserved.

All five methods passed in a private user, filesystem, and network namespace
with synthetic credentials and loopback-only peers. The historical fixture's
update-cache version remains synthetic and does not change the selected
oracle. These cases do not establish complete provider, lifecycle, security,
or other-platform parity.
