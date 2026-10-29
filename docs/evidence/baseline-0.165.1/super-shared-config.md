# Shared Codex config in DeepSeek Super

The 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and
the frozen 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`
copy the selected Codex config into the isolated provider home. The DeepSeek
launch supplies its explicit provider and model overrides to the child. The
catalog builder reads string-valued `model_context_window` and
`model_auto_compact_token_limit` from the effective config, validates both as
unsigned integers greater than one, and clamps the latter below the context
window. Numeric TOML values are not selected by that string lookup. The two
releases differ in other catalog entries and reasoning metadata; Modex still
uses the frozen 0.439.2 catalog shape.

Modex now preserves a valid shared `config.toml` without restricting its keys,
keeps the existing owner, type, permission, size, link, and identity checks,
and copies it to the isolated child home. It resolves the tested DeepSeek
runtime settings and catalog limits. A missing explicit profile is reported
before valid TOML settings are evaluated; malformed TOML is rejected before
that profile diagnostic. Other existing shared home data is still refused so
it is not overwritten without the missing storage lifecycle.

`tests/test_super_shared_config_01651_04392.py` uses actual Super processes,
isolated homes, synthetic credentials, a loopback provider, and a synthetic
Codex child. It compares exact preserved config, provider request body and
authorization, catalog limits, invalid values, and selected profile error
ordering across both checksum-pinned Linux releases and Modex. Full catalog
contents are compared with the frozen 0.439.2 reference; the 0.165.1 catalog
shape difference is not counted as parity. The synthetic child observes the
config and provider path, but does not prove a real Codex client's behavior
for every setting. Profile lifecycle, persistent home merging, malformed-TOML
diagnostic equivalence, non-Linux targets, and general config behavior remain
unverified.

On Linux x86-64, the production build, eight shared-config/DeepSeek cross-release
methods, 19 Super launch methods, 34 provider-tools/web-search methods, the
native Super argument program, the 71-file production import audit, and the
50-native/138-Python test census passed. Reproduce the focused comparisons:

```sh
python3 scripts/ci/run-unittest.py test_super_shared_config_01651_04392.py test_deepseek_web_search_mode_01651_04392.py
```
