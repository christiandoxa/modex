# DeepSeek Super API key environment resolution

The 0.165.1 and 0.439.2 Linux processes accept `--api-key` before
`DEEPSEEK_API_KEYS`, then `DEEPSEEK_API_KEY`. The plural value splits on comma,
semicolon, and newline; surrounding whitespace and empty entries are discarded.
A present plural variable containing only empty entries is an error and does not
fall back to the singular value. Singular and explicit values reject empty
strings and whitespace. With multiple plural keys, the releases use the first
key for the first request.

Modex now resolves explicit, singular, and one-entry plural keys through its
production Super path. It rejects a multi-entry plural value before creating a
Codex child or contacting the provider because per-request rotation is not
implemented. This is a retained functional mismatch, not rotation parity.

There is also a security behavior difference. Both releases pass the original
DeepSeek key environment variables to Codex `--version` and `app-server --help`
probes, although their final Codex launch child has both variables removed.
Modex removes both variables from every Codex child, including probes. The
synthetic child fixture captures these environments; selected keys do not
appear in output or Codex argument vectors. Modex also avoids persisting the
environment values in the fixture capture. This is an intentional safer
difference from the releases.

The three real-process methods in `tests/test_super_launch.py` compare the
singular and plural paths, all three separators, explicit-key precedence over
malformed unused environment values, empty and whitespace errors, missing
keys, provider Authorization, Codex environment/argv, and the multi-key gap
against both pinned releases and Modex. Tests use only synthetic credentials,
isolated homes and a loopback provider. `make build` and the three focused
methods passed on Linux x86-64. Public network, TLS, other release targets, and
multi-key rotation remain unqualified.
