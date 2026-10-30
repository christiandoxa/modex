# Super rollout weight diagnostics against frozen releases

The pinned Prodex 0.165.1 source at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and frozen 0.439.2 source at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` declare
`--rollout-budget-sampling-weight` and `--rollout-budget-prefill-weight` as
`f64`. Before the Codex positional tail, Clap rejects invalid values with exit
2; after `exec`, the Super tail scanner returns exit 1. Both releases report
`invalid float literal` for malformed values and
`cannot parse float from empty string` for an empty value.

Modex previously accepted any spelling for these values, so a later
`--help` masked invalid input and returned success. The parser now validates
the Rust decimal and exponent grammar, optional sign, and case-insensitive
`nan`, `inf`, and `infinity` spellings. It preserves the original accepted
value, rejects whitespace, Unicode digits, underscores, `f/F` suffixes,
hexadecimal floats, malformed exponents, and trailing bytes, and treats
overflow and underflow spellings as valid as both references do.

Mojo 1.2.0 publicly exports `std.collections.string.atof`; its implementation
strips whitespace, a leading plus, and an `f/F` suffix. Its infinity parser
also accepts the intermediate `in` spelling after removing `f`. Those
conveniences differ from Rust `f64::FromStr`, so the production parser uses a
small byte scanner instead. It has no Python, native-binding, or `atof`
dependency. The native test rejects an embedded NUL; argv cannot carry NUL to
the production CLI.

The focused test compares 30 valid and invalid spellings for both options
against checksum-pinned 0.165.1 and 0.439.2 processes and Modex. A separate
manual differential matrix covered 54 spellings per option; both options had
zero mismatches and no pre-help filesystem mutations. Three-process post-tail
comparisons run with a synthetic Codex child, loopback provider, isolated
homes, and a synthetic provider key. Invalid values match both release error
outputs; the child records no probes or launch, the provider receives no
request, no overlay remains, and the key is absent from output.

Reproduce with Mojo 1.2.0:

```sh
make build
make unit-build UNIT_BUILD_PROGRAMS=test_super_cli
build/tests/test_super_cli
PYTHONPATH=tests python3 -m unittest -v \
  test_super_cli.SuperCliTests.test_rollout_weight_float_diagnostics_match_both_releases \
  test_super_cli.SuperCliTests.test_positional_rollout_weight_errors_match_releases_before_child_start
make ci-dependencies
git diff --check
```

This qualifies the tested Linux x86-64 CLI values and no-launch behavior only.
Rollout weight launch effects, other Super flags, other Codex versions, and the
remaining release targets are still unqualified.
