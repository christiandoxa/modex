# Prodex 0.166.0 Super argument validation

The reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its Super CLI declares
`--sub-agent-url` with a URL value parser, while `--url` and `--base-url` are
plain string options. Its `--tool` and `--require-tool` values parse through
`OptionalToolId`, which accepts `caveman`, `rtk`, `codebase-memory-mcp`,
`codebase-memory`, `cbm`, `playwright`, `playwright-mcp`, `ponytail`, and
`presidio`, case-insensitively with surrounding whitespace trimmed. These
contracts are visible in `crates/prodex-cli/src/runtime_args/launch_args.rs`,
`crates/prodex-optional-tools/src/optional_tools.rs`, and
`mojo/prodex_core/optional_tools_policy.mojo` at that commit.

The pinned `--sub-agent-provider` parser calls `ProviderId::parse` and reports
the ordered canonical provider IDs on an invalid value. Its registered aliases
and trim/case rules come from `crates/prodex-provider-core/src/implementation_registry.rs`,
`crates/prodex-provider-core/src/implementation_registry/mojo.rs`, and
`mojo/prodex_core/provider_registry.mojo`.

The tag-retention behavior is in Prodex release tooling: `scripts/npm/release-run-lib.mjs::syncReleaseMetadata`
fetches with `--no-prune-tags`, and `scripts/npm/release-run.test.mjs` creates a
local-only `local-evidence` tag with `fetch.pruneTags=true` and verifies it
survives `--only sync`. Modex has no npm release runner; its only source fetch
is `scripts/ci/reference.py::acquire_source`, which initializes a temporary
checkout and fetches one pinned commit for CI reference acquisition.

Modex now reports typed `--sub-agent-url` failures like the release and rejects
unknown optional-tool IDs before a later `--help`. Plain URL options defer
validation until launch validation, so help is not blocked; invalid URLs still
fail before startup. The `--sub-agent-provider` option now accepts and
canonicalizes the release's IDs and aliases. Invalid separated and attached
values match the release's typed error before later help flags; an earlier help
flag still wins. `LOCAL_OPENAI` normalizes to `local` before the URL requirement
check. The requested release-run tag-retention behavior has no Modex release
synchronization path, so this change covers the connected Super CLI parser.

Checks run from the isolated Modex worktree:

- `make BUILD_DIR=build build` — passed with existing unused-variable warnings.
- `mojo run -I src tests/test_super_cli.mojo` — passed.
- `MODEX_BINARY=build/modex PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu PYTHONPATH=tests python3 -m unittest test_active_baseline_01660.ActiveBaseline01660Tests.test_sub_agent_provider_aliases_and_errors_match_active_release test_active_baseline_01660.ActiveBaseline01660Tests.test_super_help_and_selected_parser_cases_match_active_release test_active_baseline_01660.ActiveBaseline01660Tests.test_super_validated_option_values_match_active_release test_active_baseline_01660.ActiveBaseline01660Tests.test_super_runtime_url_validation_stays_before_startup -v` — four tests passed against the checksum-verified 0.166.0 oracle.
- `python3 scripts/ci/check-product-dependencies.py` — passed; production sources still use only standard-library and internal imports.

The process comparisons use `bwrap --unshare-all`, an empty synthetic HOME,
empty PATH and no credentials. They verify no files are created for parser
errors or help. The URL startup-boundary test checks invalid `--url` and
`--base-url` values before and after `exec`, plus repeated `--url` values;
every case exits before startup. This slice verifies argument handling only:
it does not qualify delegated execution, the still-guarded Super runtime,
Guardian routing, or any of the other five release targets. This evidence uses
only the verified Linux x86-64 oracle.

## Sub-agent URL boundary whitespace

Prodex 0.166.0's `parse_sub_agent_url` validates through `Url::parse` and then
returns `value.to_owned()`. Its sub-agent config keeps that string, so URL
parsing accepts boundary whitespace while retaining the original downstream.
Modex accepts only surrounding ASCII spaces, validates a trimmed view, and
retains those spaces in its parsed option. It continues to reject CR/LF and
all C0/DEL bytes anywhere in the raw value, even though the reference accepts
the tested controls. This keeps control bytes out of the unimplemented
sub-agent runtime. It does not change `--url` or `--base-url`.

The focused process matrix covers boundary spaces and rejects non-ASCII
whitespace, credentials, query, fragment, invalid ports and IPv6; all cases
leave state unchanged. The reference also accepts CR/LF/C0 controls, empty
userinfo (`@host`), tabs inside a host, and a padded triple-slash URL that its
URL parser normalizes. Modex keeps rejecting those inputs to avoid passing
control-bearing or rewritten authorities downstream. These conservative
differences remain explicit and are not counted as parity. A Modex process
check confirms that an accepted space-padded URL still reaches the existing
Super startup guard without creating state; no sub-agent request is sent.

Super's invalid reasoning-effort diagnostic now escapes the tested U+200B and
U+2066 format characters in its Rust-style `got` value, matching the active
release. The process regression also checks that ESC and U+001F stay escaped
and that parser errors create no state. The original value field may still
contain these non-ASCII characters, as it does in the reference; this qualifies
only the selected debug-value ranges, not full Unicode `Debug` formatting.

Final checks from the detached worktree:

- `make BUILD_DIR=build build` — passed with existing unused-variable warnings.
- `mojo run -I src tests/test_super_cli.mojo` — passed, including raw space retention.
- Sixteen focused 0.166.0 Super, doctor and Gateway process tests passed.
  Oracle cases run with the verified binary inside `bwrap --unshare-all`, with
  synthetic HOME and empty PATH. Gateway parser coverage includes
  `GatewayDefault01660Tests.test_dry_run_and_config_flags_remain_parser_errors`.
- `python3 scripts/ci/check-product-dependencies.py` — passed; all 72 Mojo
  production files use only standard-library and internal imports.
