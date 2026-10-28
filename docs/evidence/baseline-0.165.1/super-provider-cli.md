# Super provider parsing against the pinned releases

`tests/test_cli_01651.py` compares the production Modex process with the
SHA-256-verified 0.165.1 oracle. The same focused scenarios in `tests/test_cli.py`
compare with the historical 0.439.2 oracle after it is acquired. Both use
synthetic homes and an isolated process sandbox.

The pinned source declares the external provider field as a Clap value parser
in `crates/prodex-cli/src/runtime_args/launch_args.rs`; its accepted aliases
and validation message come from `parse_super_external_provider` in
`crates/prodex-cli/src/runtime_args.rs`. Modex now keeps that parser error in
the CLI error path before positional Codex arguments begin.

Invalid `--provider` values before the positional Codex argument now reproduce
Clap's exit-2 diagnostic, including the original value's spelling and spaces.
The `claude`, `github-copilot`, and `github_copilot` aliases, mixed-case
`DEEPSEEK`, and help-before-option ordering are accepted as in both releases.
These parser cases make no home mutations.

The adjacent `super exec --provider=local --help` case reaches runtime argument
validation in Prodex and emits the same error text as Modex, but the release
creates profile and housekeeping lock state while Modex fails before startup.
That startup-state mismatch is recorded by the test; this comparison does not
qualify its filesystem or full Super contract parity.
