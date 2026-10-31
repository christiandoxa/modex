# Buffered provider metadata

The checksum-verified Prodex 0.166.2 Linux release and Modex production
executable were compared through their Super and local relay paths. Four
synthetic buffered chat responses cover populated, blank, empty, and colliding
provider metadata, including preservation of a request-local tag. The test
compares the actual request and response structures, checks exactly one
synthetic upstream POST per case, and verifies the synthetic authorization
header.

`tests/test_provider_metadata_01662.py` reuses the historical synthetic corpus
but selects the active 0.166.2 oracle and verifies its digest. The local run
used private user, filesystem, and network namespaces with loopback only; no
real provider credentials or traffic were used. All four cases passed on
Linux x86-64. This does not qualify streaming, other provider shapes, native
session resume, other release targets, or overall provider parity.
