# Strict beta URL validation

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The 0.166.0 Linux release accepts `http://127.0.0.1:/beta` and normalizes the
empty port to 80. Modex's strict-tools policy rejects an explicitly empty port
as malformed. The generic loopback parser still accepts it and remains
unchanged. The reference observation used synthetic configuration and a fake
Codex process with no provider request.

Before this fix, an environment-supplied beta URL bypassed Modex's strict
validator, so the existing invalid-URL regression failed. Strict validation now
runs for both configured and environment values; it rejects a trailing colon
before default-port normalization. Native tests cover valid explicit IPv4 and
IPv6 ports and the empty-port rejection. Existing local rewrite tests cover
invalid and valid environment values without exposing their contents.

This is an intentional stricter behavior than the active release. It does not
establish strict-tools or other platform parity.
