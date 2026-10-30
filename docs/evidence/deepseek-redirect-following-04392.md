# DeepSeek redirect following

The frozen Prodex 0.439.2 source uses the shared Reqwest async client for
DeepSeek upstream requests. Its default redirect policy follows bounded HTTP
redirects and applies Reqwest's method rules. Modex now follows the tested
same-origin redirects in its numeric-loopback transport.

Real Super process comparisons use the checksum-verified 0.165.1 and 0.439.2
Linux binaries, Modex, isolated synthetic homes, loopback-only peers, and
synthetic API keys. The status matrix confirms POST becomes GET for 301, 302
and 303; 307 and 308 preserve method and body. Checks also cover relative,
absolute, and query-bearing references, body-header removal for GET, the
redirect limit, final streamed response selection, missing Location, and
non-redirect 3xx responses. Same-origin requests retain the expected
authorization and provider headers.

Cross-origin redirect behavior intentionally remains restricted: unlike both
Prodex binaries, Modex returns the original 3xx without following it. This
keeps credentials and request bodies on the admitted numeric-loopback origin.
HTTPS and other origins remain unsupported, so this work does not qualify
general provider transport or URL security.

Validation on Linux x86-64:

- `test_deepseek_continuation.DeepSeekContinuationTests`: 35 tests passed
  against a freshly built production Modex binary and both pinned releases.
- Two native transport redirect tests passed for the shared request deadline
  and cancellation across a redirect; the native transport header test passed.
- `test_provider_passthrough.ProviderPassthroughTests`: 3 tests passed.
- Production Super binary/binary-passthrough comparison: 1 test passed.
- Production build, three focused native builds, product dependency audit,
  Python compilation, and `git diff --check` passed.

All peers, ports, paths, and credentials were synthetic. No account login or
provider traffic was used.
