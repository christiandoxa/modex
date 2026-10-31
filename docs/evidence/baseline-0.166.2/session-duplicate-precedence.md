# Prodex 0.166.2 session duplicate-option precedence

The connected `session list` and `session current` parser now checks the next
argument before returning a duplicate value-option error. This matches the
pinned release when a malformed attached boolean/help value or an unknown
argument immediately follows a repeated value option. Unknown-argument usage
retains earlier accepted options while omitting only the duplicated option. A
valid next switch, typed `--limit` failure, missing split value, later malformed
switch, or repeated boolean switch retains the duplicate diagnostic.

`tests/test_session_duplicate_precedence_01662.py` compares 15 process cases
against the checksum-verified Linux x86-64 0.166.2 binary. Every case uses a
fresh synthetic home and workspace; the comparison checks exact exit status,
stdout, stderr, and the absence of filesystem changes. The test is registered
in the active fast and full CI lanes.

This qualifies only the listed session parser precedence cases on Linux x86-64.
It does not establish complete session CLI or session contract parity.
