# Guardian profile affinity does not apply to DeepSeek API keys

The verified active release is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its Guardian parent lookup is in
`crates/prodex-app/src/runtime_proxy/payload_detection.rs`: it accepts the
exact `x-codex-guardian: reviewer` marker and reads
`client_metadata.parent_response_id`. The profile-backed Responses path uses
that owner as strict continuation affinity in
`crates/prodex-app/src/runtime_proxy/responses/affinity_state.rs`; quota
failures return without rotating away from that parent in
`crates/prodex-app/src/runtime_proxy/responses/quota_blocked.rs`.

The verified Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.
The separate
`super --provider deepseek` API-key path rotates keys and does not apply
profile Guardian affinity. The pinned source's API-key selector starts from
its rotating cursor and enumerates the key pool in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_transport.rs`;
its DeepSeek sender uses that attempt list in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs`.
A real-process comparison against the checksum-verified 0.166.0 oracle confirms
that distinction using two
synthetic keys, a successful parent response, a reviewer request with its
parent response ID, and a synthetic quota response. Both Prodex and Modex
send `synthetic-key-a`, then `synthetic-key-b`; after the reviewer request's
429 they retry with `synthetic-key-a` and return success. The test uses local
loopback upstream fixtures only.

Set `PRODEX_ORACLE` to the verified 0.166.0 binary outside `/tmp`, then run
the focused differential with a private temporary filesystem and network
namespace from the checkout:

```sh
unshare -Urnm sh -c 'mount --make-rprivate / && mount --bind "$PWD" /mnt && mount -t tmpfs -o mode=1777 tmpfs /tmp && ip link set lo up && mkdir -m 700 /tmp/home /tmp/work && cd /mnt && exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE="$PRODEX_ORACLE" PYTHONPATH=tests python3 -m unittest test_guardian_api_key_01660 -v'
```

This does not implement profile Guardian affinity or routing-cookie retention.
The Modex profile broker and Codex Responses proxy path remain missing; API
keys are not profiles. The existing `GUARDIAN-01660-AFFINITY` release status
remains `NOT_STARTED`.
