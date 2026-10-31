# DeepSeek streamed item identities

`tests/test_deepseek_stream_ids_01662.py` runs the existing synthetic item-ID
corpus against the checksum-verified Prodex 0.166.2 Linux oracle and production
Modex. Two real-process tests compare stream event identities and verify unique
local sequences across concurrent requests. The historical fixture's update
cache remains synthetic; it does not select or replace the active oracle.

Both tests passed in a private user, filesystem, and network namespace with
loopback-only synthetic peers. No real credentials or provider traffic were
used. These cases do not establish full streaming, connection ownership,
lifecycle, or other-platform parity.
