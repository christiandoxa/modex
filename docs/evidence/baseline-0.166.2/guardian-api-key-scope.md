# Guardian metadata on the API-key route

`tests/test_guardian_api_key_01662.py` runs the existing synthetic Guardian
metadata corpus against the checksum-verified Prodex 0.166.2 Linux oracle and
production Modex. Two real-process tests compare API-key selection for a
parent and reviewer request, including a synthetic quota retry. They check the
exact synthetic authorization sequence and response status. The historical
fixture's update-cache version does not select the oracle.

Both tests passed in private user, filesystem, and network namespaces with
loopback-only synthetic peers. No real credentials or provider traffic were
used. These controls do not establish profile-backed Guardian parent or
continuation affinity, cookie routing, WebSocket reuse, or other-platform
parity.
