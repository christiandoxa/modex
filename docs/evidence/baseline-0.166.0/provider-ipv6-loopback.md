# IPv6 loopback URL authorities

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The release accepts equivalent IPv6 loopback spellings such as `[::01]`,
`[0:0::1]`, and `[::0.0.0.1]`, and sends the canonical `[::1]` Host authority.
The previous Modex URL boundary accepted only `[::1]`. It now validates IPv6
syntax and accepts only values representing exactly `::1`, then passes the
canonical loopback address to the existing transport. Unspecified, non-loopback,
IPv4-mapped, scoped, and malformed addresses remain rejected before a request.

The active authority process test compares five equivalent spellings through
real Prodex and Modex Super processes with a synthetic IPv6 loopback provider;
it also compares one Anthropic Messages request and tests selected rejection
controls. Native Gateway assertions cover those validation boundaries. These
tests do not qualify other IPv6 forms, external destinations, or other release
targets.

The production build, native Gateway test, production import audit, and all
five authority process tests passed locally. The process tests used synthetic
credentials, isolated temporary state, and a private network namespace with
only loopback enabled. An initial namespace run without private `/tmp` failed
before the oracle launched its provider bridge because the oracle rejected its
runtime secret location; mounting private temporary storage resolved that
environment failure without changing the oracle or its security checks.
