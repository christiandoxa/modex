# Provider passthrough and redirect qualification

`tests/test_provider_passthrough_01662.py` runs 20 selected synthetic
passthrough cases against the checksum-verified Prodex 0.166.2 Linux x86-64
release and the Modex executable built from source commit
`08578e288f4a525171c21b72de49ce9b1c82f9c9`. The oracle SHA-256 is
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`; the
Modex executable used for this run has SHA-256
`f81d300cb30bba455b2636f57ada0b7dd5c00c7d4bc219643811e9a35bead611`.

The corpus covers buffered and streamed response metadata, 503 header casing,
redirect authority and path/query handling, empty `Location` behavior and loop
limits, provider route aliases and model catalog methods, local client
authentication, CONNECT handling, duplicate `Content-Type` classification,
bodyless response framing, and same-connection reuse. Each case uses synthetic
keys, temporary home/state/work directories, and local loopback peers. No
provider credentials or external provider requests are used.

All 20 selected comparisons passed in 55.174 seconds through the strict
`scripts/ci/run-unittest.py` runner. The active wrapper asserts the exact
discovered method set, preventing inherited historical cases from silently
entering or leaving this corpus. Its synthetic update-check marker is set to
`0.166.2`; the historical module retains its `0.166.0` default and behavior.
The full 21-case historical suite also passed against the pinned 0.166.0
oracle in 71.243 seconds with the same Modex executable.

The malformed-SSE open-stream mismatch is excluded from this parity corpus.
The active `test_provider_shapes_01662.py` suite separately requires Modex to
terminate the failed stream and records that the pinned oracle leaves its
downstream response open; this divergence is not counted as a match. This
qualification found no production mismatch and does not establish complete
provider parity, security parity, or parity for the other five release
targets.
