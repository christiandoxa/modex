# Unicode numeric loopback hosts (Prodex 0.166.0)

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

Prodex's `validate_credential_free_http_url` validates the configured URL with
`reqwest::Url::parse`; `local_rewrite_transport/urls.rs` then combines the
base URL with the provider route. Active process comparisons show that this
accepts `１２７．１`, `127。1`, `127｡1`, `１２７.1`, `127．１`, and the
percent-encoded Unicode dot `127%EF%BC%8E1`; each synthetic provider request
uses canonical `Host: 127.0.0.1:<port>` and returns 200. Before this fix,
Modex rejected those numeric authorities before making an upstream request.

`url_numeric_host_compatibility` maps only fullwidth decimal digits
U+FF10–U+FF19 and IDNA dot equivalents U+FF0E, U+3002, and U+FF61. URL
authority validation uses that mapped spelling for its numeric-host checks;
`normalize_loopback_ipv4_host` then passes it through the existing IPv4 parser.
The assembled-address check still requires `127/8`, and the relay still
connects directly to canonical numeric IPv4 without DNS. Modex process controls
reject `１２８．１`, duplicate dots, and a fullwidth at sign before provider I/O;
the native guard also rejects a fullwidth slash. The oracle rejects the
fullwidth hexadecimal spelling
`０ｘ７ｆ００００００１` and its percent-encoded form, so this change does not
map fullwidth letters.

`tests/test_provider_base_url_authority_01660.py` exercises the real production
relay against the checksum-verified oracle with a synthetic provider key and
loopback server. Its accepted cases compare status, canonical Host, route,
authorization, and translated request bytes. The run uses isolated temporary
HOME/state and a private network namespace containing only loopback, with no
default routes. Native Gateway checks cover the narrow Unicode mapping and
rejection controls.

This covers only the listed Unicode digit and dot forms on Linux x86-64. It
does not implement general IDNA/UTS-46 processing or establish full provider
or release-target parity.

## Validation

- `make BUILD_DIR=/tmp/modex-active-provider-build build` passed with Mojo
  1.2.0.
- `make BUILD_DIR=/tmp/modex-active-provider-build UNIT_BUILD_PROGRAMS=test_gateway_cli UNIT_RUNS=test_gateway_cli unit`
  passed; native Gateway argument checks reported `PASS`.
- `test_provider_base_url_authority_01660` passed 6 tests against the verified
  oracle in a private user, mount, and network namespace. Only loopback was
  present, default routes were empty, the workspace and oracle were read-only,
  and HOME, TMPDIR, and `/tmp` were isolated.
- `make ci-dependencies` passed; production import audit found 74 Mojo files
  using only standard-library/internal imports.

The active authority module is already included in Fast and Full CI. The local
run does not establish hosted CI success.
