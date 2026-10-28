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

TOML configuration precedence, non-loopback transport, broader request shapes,
and complete error and resource equivalence remain unverified or unsupported.
No provider contract, platform obligation or release qualification is promoted.
