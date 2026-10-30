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
