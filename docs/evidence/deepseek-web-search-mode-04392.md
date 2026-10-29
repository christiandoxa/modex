# DeepSeek web-search mode against Prodex 0.439.2

The reference is the official Linux x86-64 0.439.2 binary at SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`,
from source commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The
frozen runtime configuration and DeepSeek local-rewrite source were traced.

The production Super relay now reads `PRODEX_DEEPSEEK_WEB_SEARCH_MODE`.
Selected real-process comparisons show `off`, `disable` and `disabled` reject
search requests before any upstream POST; `openai_chat`, `openai-chat` and
`chat` route them to Chat Completions; and `auto` and `anthropic` use the
Messages route for the tested web-search request. Case-insensitive aliases,
non-search requests, empty input, raw Chat Completions passthrough, strict
beta routing and invalid environment values are also covered. Normal successful
routing comparisons check complete request and response JSON apart from
generated timestamps; the strict-beta control checks the route and request
JSON. Rejected requests compare status, body and POST count.

Before the fix, Modex sent a POST for the three tested off aliases and sent
the chat aliases to Messages instead of Chat Completions. Invalid mode values
were also ignored. Tests use isolated HOME and synthetic loopback peers; no
real credentials, account login or paid provider traffic are used.

On the combined Linux x86-64 build, `make build`, the five methods in
`python3 scripts/ci/run-unittest.py test_deepseek_web_search_mode_04392.py`,
the two rebuilt provider native tests, and all 19 methods in
`test_local_rewrite.py` passed. The production dependency audit passed for
all 71 listed Mojo sources.

## Mode-only TOML configuration (2026-10-29)

Both the 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and the frozen 0.439.2 source resolve `deepseek.web_search_mode` from the
selected Codex home's `config.toml` before consulting the environment. Real
Super process controls against both checksum-pinned binaries verify `off`,
`openai_chat`, `anthropic`, and `auto` routing even when the environment
requests a different or invalid mode. Invalid TOML values fail before the
synthetic Codex child or upstream POST.

At this checkpoint Modex admitted a private shared home containing only a
configuration whose only setting was `deepseek.web_search_mode`. It checks the directory and file,
copies the config into the isolated child home, preserves the original file,
and passes the validated effective mode to the local relay. Tests reject
group-writable files, symlinks, and exposed hard links before launching the
child. The later strict-tools and beta configuration extension is documented
in `docs/evidence/deepseek-strict-tools-04392.md`, and broader config copying
in `docs/evidence/baseline-0.165.1/super-shared-config.md`. Existing home data
remains guarded until its lifecycle is implemented. Malformed TOML and
unsafe-file diagnostics remain potentially different from the releases.

The production build, 10 mode tests, 40 neighboring local-rewrite and Super
tests, native Super parser check, 71-file dependency audit, and 50-native/
137-Python test census passed. After adding the final size and private-mode
checks, the production build and three focused cross-release/safety methods
passed again.

Run the active and cross-release comparisons with:

```sh
python3 scripts/ci/run-unittest.py test_deepseek_web_search_mode_04392.py test_deepseek_web_search_mode_01651_04392.py
```

The process comparisons use synthetic credentials and loopback-only peers;
they do not cover non-loopback transport, broader request shapes, full TOML
configuration, or complete error and resource equivalence.
No provider contract, platform obligation or release qualification is promoted.
