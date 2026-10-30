# Duplicate Content-Type on DeepSeek passthrough

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`, with Linux x86-64 oracle SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The tested buffered passthrough responses retain the last valid
`Content-Type` value at the first occurrence's position. Modex previously
forwarded both. It now follows that behavior for buffered passthrough while
preserving duplicate `Set-Cookie` and unrelated headers, header order, and
existing hop-by-hop filtering. The tested streaming path still forwards both
Content-Type fields, matching the release. The first Content-Type continues to
select buffering or event streaming in both tested orders.

Active process tests cover Chat Completions 200, Responses 503, both mixed
JSON/event-stream header orders, repeated cookies and custom fields, and a
Connection-nominated hop-by-hop field. They use synthetic credentials and
providers, isolated temporary state, and loopback-only networking. This is
limited to tested Linux x86-64 responses; malformed header values, other
routes, and other release targets remain unqualified.
