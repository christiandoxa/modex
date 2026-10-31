# Local compaction fallback

`tests/test_local_compact_01662.py` runs the existing synthetic compaction
corpus against the checksum-verified Prodex 0.166.2 Linux oracle and production
Modex. Four real-process methods compare selected request/input shapes,
long model whitespace, JSON nesting boundaries, and route controls. The
fixture preserves its historical inputs while selecting the active oracle.

All four methods passed with private user, filesystem, and network namespaces
and synthetic loopback peers. No real provider traffic or credentials were
used. This does not establish complete compaction, provider, lifecycle, or
other-platform parity.
