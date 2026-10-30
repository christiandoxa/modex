# Codex 0.166.0 isolated loopback check

The official OpenAI `rust-v0.166.0` Linux x86-64 musl archive
`codex-x86_64-unknown-linux-musl.tar.gz` was downloaded separately from the
installed Codex. Its SHA-256
`a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978`
matches the GitHub release asset digest. The extracted executable SHA-256 is
`b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8`
and it reports `codex-cli 0.166.0`. The installed Codex was not changed.

`tests/manual_real_codex_local_auth.py` passed with this executable and the
Modex build from `94b514c2fe3992a9f2219b035746820f8fe17161`. It ran under
`unshare -Urn` with only loopback enabled, no IPv4 or IPv6 default route,
isolated HOME/config/storage, and synthetic provider credentials. The single
provider request went to the synthetic loopback `/v1/chat/completions` peer;
the test checked the per-launch local token, provider authorization and that
neither secret appeared in output. No login or paid provider request occurred.

Reproduce with a separately verified Codex executable and Modex build:

```sh
timeout 120s unshare -Urn env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  MODEX_BINARY=/absolute/path/to/modex CODEX_BINARY=/absolute/path/to/codex \
  NODE_BIN=/absolute/path/to/node/bin MODEX_REAL_CODEX_NETNS=1 \
  PYTHONPATH=tests python3 tests/manual_real_codex_local_auth.py -v
```

`iproute2` and user/network namespaces are required. Set
`MODEX_EXPECTED_CODEX_VERSION=0.165.0` only for the historical client check.
This single local-auth case does not establish general Codex 0.166.0,
Guardian, WebSocket, profile-routing or platform parity.
