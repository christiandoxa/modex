# DeepSeek metadata-only Chat Completions stream chunk

The production Super route was exercised with checksum-pinned Prodex 0.165.1,
Prodex 0.439.2, and Modex processes against an isolated loopback peer. The
synthetic SSE stream starts with a metadata-only chunk (`choices: []`) carrying
the response ID, model, creation time, system fingerprint, and usage; it then
sends text, a `stop` finish chunk, and `[DONE]`. All three processes returned
200 and emitted the same normalized event sequence. The completed response
retained the ID, model, usage from the first chunk, and the DeepSeek system
fingerprint.

The frozen source at Prodex commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` and historical source at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` both apply chunk metadata before
selecting the first choice in
`crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs::RuntimeDeepSeekSseState.observe_chat_chunk`.
The provider-core metadata projection is in
`crates/prodex-provider-core/src/translators/deepseek/stream/shaping.rs::deepseek_provider_core_stream_chunk_metadata`.
Modex follows this order in `src/modex/provider_chat_stream.mojo` through
`DeepSeekChatState.observe` and `apply_metadata`.

Oracle SHA-256: Prodex 0.165.1
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`; Prodex
0.439.2 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
Modex executable SHA-256:
`bfe18d1f990d2b27808521640029aa54c8659ca5eeac2e20ee9320bfe7c0269a`.

Reproduce from the repository root with the pinned local binaries available at
the default paths:

```sh
PYTHONPATH=tests python3 -m unittest -v \
  test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_deepseek_metadata_only_chat_chunk_matches_shared_releases
```

This qualifies only the listed Linux x86-64 stream shape. It does not establish
complete streaming behavior, security behavior, or parity across all six
baseline release targets.
