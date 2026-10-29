# Gateway DeepSeek config classification against frozen releases

Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`), 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`), and historical 0.439.1
(`81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`) all route `gateway` through
`handle_gateway` and `prepare_gateway_runtime`. The handler reports
`gateway provider does not expose an OpenAI-compatible proxy` when the prepared
launch has no OpenAI proxy. The `prepare_gateway_runtime` implementation is
the same in all three pinned sources: it builds a runtime launch with the
selected Codex config and requests proxy preparation.

Verified Linux oracle SHA-256 values are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
for 0.165.1, `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
for 0.439.2, and `b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a`
for 0.439.1.

Real-process controls used checksum-verified Linux release executables and
private synthetic homes. The Codex config selected
`model_provider = "prodex-deepseek"` plus either an additional top-level model
setting or a nested project setting. All three releases exited 1 with the
same no-proxy diagnostic and made no request to the synthetic loopback peer.
Before the fix, Modex returned its generic unsupported-config diagnostic
because it only recognized the DeepSeek provider when it was the sole
top-level TOML key.

Modex now checks the parsed `model_provider` independently of other Codex
settings. `tests/test_gateway_launch_01651.py` compares the production binary
with checksum-pinned 0.165.1 and 0.439.2, and with 0.439.1 when that historical
oracle is available. The test uses isolated HOME, Codex config, application
state, and a local loopback peer; it sends no provider request and contains no
real credential.

Additional process controls cover empty config, duplicate and malformed root
TOML, a provider value only under a project table, group-writable root-provider
configs with extra settings, and a present `state.json`. All three releases and
Modex return the same no-profile error with no config. Duplicate and malformed
TOML fail before provider setup in every binary; parser diagnostics differ, so
the test checks rejection and absence of loopback traffic rather than exact
error text. With a project-only `model_provider`, all three releases and Modex
return the no-profile error. Modex now classifies only the root
`model_provider` for the profileless DeepSeek proxy case, matching the pinned
launch selection: it reads the shared Codex home, selects a profileless local
home only for a supported root provider, then resolves an active profile.
With mode `0664`, releases return the no-proxy error while Modex retains its
stricter group-write guard, including when unrelated settings are present. A
Modex-only `state.json` control returns the existing-state unsupported
diagnostic before config classification; it does not establish release parity
for populated profile state.

The comparison covers only this failed-startup classification. It does not
qualify successful Gateway startup, other Codex config shapes, provider
exchange, or lifecycle/housekeeping filesystem effects. Those filesystem
deltas remain a documented parity mismatch in
`docs/evidence/gateway-mismatch.json`; no placeholder locks are created.

Run after the production build and oracle acquisition:

```sh
python3 scripts/ci/run-unittest.py test_gateway_launch_01651.py
```

On 2026-10-29, `make build`, all six methods in that real-process comparison,
the native Gateway argument program, and 17 focused Gateway process/CLI tests
passed. The comparison included all three local release oracles. The production
import audit passed for 71 Mojo files; the test-census audit passed for 50
native test sources and 136 Python modules. The project-only `model_provider`
case compares the exact no-profile diagnostic and asserts that Modex performs
no filesystem mutation or loopback request.
