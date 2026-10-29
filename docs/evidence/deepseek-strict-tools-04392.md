# DeepSeek strict-tools and beta-route slice

The frozen reference is Prodex 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; the verified Linux oracle SHA-256
is `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
This evidence covers the strict function-tool setting, schema normalization,
and beta chat-completions route only. It does not change the parity denominator
or claim whole-provider parity.

The initial strict-tools slice was environment-only:
`PRODEX_DEEPSEEK_STRICT_TOOLS` enables normalization and
`PRODEX_DEEPSEEK_BETA_BASE_URL` selects a beta route. The existing bounded
numeric-loopback URL parser validates the beta URL before Super creates an
overlay or starts Codex. Unsafe values fail with a generic diagnostic that
does not echo URL contents. Strict runtime-path schemas use the beta route.
The frozen simple-request pass can preserve a nested tool unchanged, even
when strict mode is enabled; selected production comparisons match this.

At that checkpoint, TOML settings were not propagated into the private overlay,
so the real 0.439.2 TOML-only strict-tools control exposed a Modex mismatch.
The later connected TOML implementation is described below.

Synthetic loopback tests exercise enabled and disabled environment settings,
trailing-slash normalization, strict schema fields, invalid booleans, and
credential/query/fragment/whitespace/empty/unsupported URL rejection. A real
Super launch comparison against the pinned release confirms env-based beta
routing and normalized schema parity. Separate real launch controls captured
the then-open config-only mismatch and verify unsafe beta URLs fail before profile or
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
selected environment-backed URL validation cases; general TOML propagation, public beta
transport, and complete Unicode hostname normalization remain unsupported.

## TOML strict-tools and beta settings (2026-10-29)

The 0.165.1 and 0.439.2 configuration readers resolve
`deepseek.strict_tools`, `deepseek.beta_base_url`, and
`deepseek.web_search_mode` from the selected Codex config before their
environment settings. Strict tools accepts booleans and recognized boolean
strings. The beta URL reader ignores non-string and whitespace-only TOML
values and then consults the environment. Other configured beta values are
validated even when strict mode is off.

Modex now admits these three settings individually or together in a private
shared config, copies that config to the private child home, and carries the
validated effective settings to the production relay. A real Super process
comparison against both checksum-pinned Linux releases checks strict beta
routing and schema conversion, conflicting and invalid environment values,
boolean/string strict settings, invalid config and beta fallback. Tests use
synthetic credentials and a numeric loopback peer. The 1 MiB config limit,
ownership and file checks remain enforced. The later shared-config extension
preserves other settings; existing Codex state remains guarded, and public
WSS/TLS/DNS and other targets remain unverified. See
`docs/evidence/baseline-0.165.1/super-shared-config.md`.

The production build and local-rewrite driver build passed with Mojo 1.2.0.
The seven focused strict/config and cross-release methods passed; the 34-method
provider-tools and web-search suites passed against 0.439.2 and Modex, as did
the 22 local-rewrite tests, native provider-tool program, 71-file production dependency audit and
50-native/137-Python test census. Reproduce the process comparisons with:

```sh
python3 scripts/ci/run-unittest.py test_provider_tools_04392_characterization.py test_deepseek_web_search_mode_04392.py test_deepseek_web_search_mode_01651_04392.py
```
