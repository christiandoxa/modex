# Unicode-whitespace log redaction across pinned releases

The production `log last --json` path now matches Prodex 0.165.1 and frozen
Prodex 0.439.2 for an unquoted sensitive value preceded by Unicode whitespace.
Both release sources route transcript text through
`redaction_redact_secret_like_text`; their
`mojo/prodex_core/redaction.mojo::reaction_sensitive_key_value_pass` skips only
ASCII whitespace after `=`. Thus `password=\u2003synthetic-secret-value` is
treated as one unquoted value and rendered as `password=<redacted>`. Modex now
does the same while continuing to mask the value completely.

Quoted values retain Modex's complete masking even where the release leaks the
synthetic value. Multiple ASCII spaces, tabs, Unicode spaces, C0/C1 controls,
curly quotes, and zero-width separators are also exercised. Malformed
Unicode-separated values mask the rest of their line; ambiguous quote/control
boundaries fail closed for that line. This can hide trailing context on those
malformed inputs and does not claim full redaction equivalence.

The three-way fixture runs a real process for each binary, with a separate
temporary HOME, workspace, and session file, an empty PATH, and bubblewrap
network isolation. All payload values are synthetic. Binary hashes:

| Process | SHA-256 |
| --- | --- |
| Prodex 0.165.1 | `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` |
| Prodex 0.439.2 | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` |
| Modex build | `3c628cab44d29890d49acaef8d574598f19c30b81e7ac774ff4e1aaaf06e1a97` |

For `password=\u2003synthetic-secret-value`, all three processes returned the
same JSON event with `"text":"password=<redacted>"`. The focused redaction
module passed all six methods, including a 3,000-assignment stress control.
The broader direct-caller suite passed 42 methods across redaction,
`log last`, stream following, operational projection, transcript projection,
payload rendering, Super CLI, and provider stream modules.

The production import audit passed for 71 Mojo files, the census passed for 50
native test sources and 155 Python modules, workflow policy validation passed,
and `git diff --check` passed. `docs/evidence/log-mismatches.json` now retains
three release credential leaks as unapproved safe differences and three
matching outputs. This slice does not change the six-target denominator,
promote a platform contract, implement live log sources, or establish security
equivalence.
