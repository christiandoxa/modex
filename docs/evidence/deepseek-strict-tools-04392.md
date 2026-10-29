# DeepSeek strict-tools and beta-route slice

The frozen reference is Prodex 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; the verified Linux oracle SHA-256
is `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
This evidence covers the strict function-tool setting, schema normalization,
and beta chat-completions route only. It does not change the parity denominator
or claim whole-provider parity.

The supported strict-tools slice is environment-only:
`PRODEX_DEEPSEEK_STRICT_TOOLS` enables normalization and
`PRODEX_DEEPSEEK_BETA_BASE_URL` selects a beta route. The existing bounded
numeric-loopback URL parser validates the beta URL before Super creates an
overlay or starts Codex. Unsafe values fail with a generic diagnostic that
does not echo URL contents. Strict runtime-path schemas use the beta route.
The frozen simple-request pass can preserve a nested tool unchanged, even
when strict mode is enabled; selected production comparisons match this.

TOML settings are intentionally not propagated into the private overlay.
Super retains its fail-closed behavior when a shared Codex `config.toml` or
other state already exists. The real 0.439.2 characterization continues to
show that its TOML-only strict-tools configuration succeeds while Modex
rejects that config-only home before starting Codex or contacting the
provider. This config gap is not counted as parity.

Synthetic loopback tests exercise enabled and disabled environment settings,
trailing-slash normalization, strict schema fields, invalid booleans, and
credential/query/fragment/whitespace/empty/unsupported URL rejection. A real
Super launch comparison against the pinned release confirms env-based beta
routing and normalized schema parity. Separate real launch controls retain
the config-only mismatch and verify unsafe beta URLs fail before profile or
Codex launch. The disabled control keeps the regular route and schema.

Focused results from an isolated build:

- Production Modex and native loopback-driver builds passed with Mojo 1.2.0.
- `test_local_rewrite.py`: 19 tests passed.
- `test_super_launch.py`: 15 tests passed.
- `test_provider_tools_04392_characterization.py`: 7 tests passed against
  the checksum-verified 0.439.2 oracle.
- Native provider-request-tools and DeepSeek-transport checks passed.
- Product dependency audit and test-census checks passed.

The beta route must be explicitly set to numeric loopback HTTP when strict
mode is enabled. Public HTTPS/DNS URLs, including the reference default, are
unsupported by the current transport; DNS, TLS, and external-provider
transport remain gaps. With strict mode off, a valid public beta URL is
validated but remains unused for routing, so requests keep the default route.
Tests use only synthetic loopback URLs and credentials.

## 0.439.2 beta URL validation follow-up

The frozen source resolves `runtime_deepseek_beta_base_url` during DeepSeek
provider construction. It validates a configured value as HTTP(S), with a
host, and without credentials, query or fragment, even when strict tools are
disabled. The production Super preflight now applies that validation to a
present environment value before launching Codex, while keeping valid public
URLs unused when strict mode is off.

The real-process comparison covers an empty value, malformed URL, unsupported
scheme, credentials, query, fragment, whitespace, forbidden authority bytes,
malformed percent escapes, invalid decoded UTF-8, and percent-encoded invalid
numeric hosts. Modex and the pinned release both fail before Codex launch or
provider I/O, with no profile overlay left behind. Synthetic credentials in
invalid values are not echoed. Valid percent escapes, numeric hosts, raw and
encoded Unicode IDNs, punycode, and the strict loopback-route controls still
pass. Modex and 0.439.2 reject all 13 tested fullwidth ASCII mappings to
forbidden URL host characters, including percent-encoded fullwidth `@`, before
Codex/provider launch and without leaving profile overlays. This targeted
check does not implement complete UTS #46 hostname normalization; broader IDNA
equivalence remains an explicit parity gap.

Validation on Linux x86-64: `make build` and
`make unit-build UNIT_BUILD_PROGRAMS='local_rewrite_driver'` passed with Mojo
1.2.0. The full `test_provider_tools_04392_characterization` module passed all
18 tests against the checksum-verified release and production Modex CLI. The
earlier active 0.165.1 raw HTTP and invalid-URL launch controls remain
historical checks; they do not qualify full 0.165.1 behavior. These cover only
selected environment-backed URL validation cases; TOML propagation, public beta
transport, and complete Unicode hostname normalization remain unsupported.
