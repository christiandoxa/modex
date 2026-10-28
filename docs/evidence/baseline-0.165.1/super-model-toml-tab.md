# Super model TOML TAB spelling

The verified Prodex 0.165.1 Linux oracle has SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
The production Super test launches both binaries with isolated state and a
synthetic Codex child, captures the actual `app-server --stdio` preflight
arguments, and makes no upstream request.

The pinned `runtime_catalog_config::toml_string_literal` delegates to
`toml::Value::String`; `runtime_tools/app_server_args.rs` uses it when projecting
model options. Modex's captured Super path generated its model value in
`src/modex/super_launch.mojo` with the generic JSON string escaper.

For model `a<TAB>b`, Prodex passes `model="a<TAB>b"`. Before this change,
Modex passed the two-character escape `model="a\\tb"`. Python's TOML parser
accepts both and returns the same model value, but the production argv differs.
The fix preserves the TOML-permitted literal TAB only in the generated DeepSeek
model value. The complete normalized preflight argument arrays now match for
TAB, quotes, backslash-plus-`t`, mixed TAB/quote and Unicode models. Each
process exits 7, makes no upstream request and removes its temporary overlay.

The serializer retains escapes for line breaks and other control characters.
The oracle emits raw LF, CR and C0 controls inside a single-line quoted model
value; Python's TOML parser rejects those values. Modex keeps these values
parseable instead of reproducing the invalid literals. NUL cannot be passed in
process argv; the native serializer check verifies it remains escaped when
given as a `String`. Quote/backslash and newline-injection values round-trip
through the TOML parser without creating another config key.

Validation used the native `test_super_model_toml` and
`test_app_server_args` executables, plus the two production tests in
`tests/test_super_model_toml_01651.py`. Fast and Full CI route this module in
the active-reference lane before historical oracle tests. The comparison
qualifies this Linux x86-64 model-TAB case only; other release targets and the
raw-control mismatch remain unqualified.
