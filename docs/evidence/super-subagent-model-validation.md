# Sub-agent model validation

The 0.165.1 and 0.439.2 sources both use the sub-agent model parser in
`crates/prodex-cli/src/sub_agent.rs`; it rejects a model whose Unicode-trimmed
value is empty and preserves the original value otherwise. Before a positional
argument, the CLI reports a value-parser diagnostic; after `exec`, it reports
a runtime error.

`tests/test_super_subagent_model_shared.py` compares both checksum-verified
Linux releases and the production Modex CLI in isolated synthetic homes. Empty,
ASCII-whitespace and Unicode-whitespace values produce matching exit codes and
diagnostics in both positions. Before `exec`, none creates state; after `exec`,
the releases create application state while Modex still exits without it.
Valid model values preserve help ordering; the native test also verifies that
Modex keeps the original padded model value. This does not establish sub-agent
launch or state-lifecycle parity.

With both pinned oracles available, reproduce with `make build` followed by
`python3 scripts/ci/run-unittest.py test_super_subagent_model_shared.py`.
