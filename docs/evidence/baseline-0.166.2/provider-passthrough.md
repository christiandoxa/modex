# Provider passthrough and redirect qualification

`tests/test_provider_passthrough_01662.py` selects 21 methods from the
historical provider passthrough fixture and runs them against the
checksum-verified Prodex 0.166.2 Linux x86-64 release. The oracle SHA-256 is
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.
The follow-up used Modex source `4bf96280540dc984ad242e5d1cc2551a637cfe07`
plus the working-tree fix, with executable SHA-256
`fa7e09e8b8e138f0887eee128145696d17a9d8fd5f095402b8a3b7bb1efc24e4`.

The existing cases cover buffered and streamed response metadata, 503 header
casing, redirect authority and path/query handling, empty `Location` behavior
and loop limits, provider route aliases and model catalog methods, local client
authentication, CONNECT handling, duplicate `Content-Type` classification,
bodyless response framing, and same-connection reuse. Each case uses synthetic
keys, temporary home/state/work directories, and local loopback peers.

The new `test_redirect_location_utf8_controls_preserve_first_header_and_origin_guards`
regression runs real Modex and oracle processes with a loopback-only network
namespace. For invalid UTF-8 in the first `Location` value, both buffered and
streaming Chat Completions requests now retain the original 302 and body with
one upstream POST. Before the fix, Modex converted the invalid byte to U+FFFD
and followed a percent-encoded replacement path. The pinned source sends the
provider request with the default Reqwest client; its 0.166.2 behavior is to
leave that invalid first `Location` unfollowed.

The regression also confirms that ASCII, percent-encoded Unicode, valid raw
UTF-8, and a valid literal U+FFFD redirect remain followable. Duplicate
`Location` controls establish first-value semantics: an invalid first value
does not fall through to a valid second value, while a valid first value is
followed even if a later duplicate is invalid. These controls compare exact
upstream method/path, synthetic Bearer header, downstream status, and body.

A separate different-port loopback case records the existing authority guard.
The pinned release follows the cross-origin redirect and strips its synthetic
Bearer header. Modex refuses the redirect, returns 302, and makes no request to
the second peer. This is a deliberate safety divergence and is not counted as
a parity match. A duplicate with a same-origin first value and cross-origin
second value confirms both products select the first value and never contact
the second peer.

The active wrapper asserts the exact discovered method set and sets its
synthetic update-check marker to `0.166.2`; the historical fixture keeps its
`0.166.0` default. The follow-up strict runner completed all 21 selected
methods in 38.552 seconds inside Bubblewrap with loopback only. No real
credentials or external provider requests were used. This selected Linux
x86-64 evidence does not establish complete provider, security, or six-target
parity.

The earlier 20-case active comparison passed against the 0.166.2 oracle with
Modex built from `08578e288f4a525171c21b72de49ce9b1c82f9c9`; the full
21-case historical suite also passed against 0.166.0 on that build. The known
malformed-SSE open-stream divergence remains excluded from active parity and
is separately checked as a bounded Modex failure in the provider-shapes suite.
