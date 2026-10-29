# Profile identifier and retention edge probes

The production Modex binary (`fbd71493f964b8564f4e4f2bbf4b5403038324d11c4623f13eb813dd01e4f5bc`)
was compared with the checksum-pinned Prodex 0.165.1 and 0.439.2 Linux
binaries. Fixtures use synthetic state and session files in isolated homes.

One parity mismatch was found and fixed. When a binding names an existing
empty-string profile, both releases return `"profile": ""` and select it for
`--profile ""`; Modex had collapsed this present value to `null`. Session
reports now preserve binding presence with `Optional[String]`. An absent
binding still returns `null` and does not match the empty profile filter. The
new regression is
`tests/test_session_profile_04392.py::test_empty_profile_and_session_identifiers_preserve_presence`.

Other tested edges matched both releases:

- An empty session-map key does not bind the fixture's nonempty session ID.
- Profile identifiers are case-sensitive and preserve surrounding spaces;
  exact filters match and differently cased or trimmed filters do not.
- Duplicate valid profile-map keys are accepted; duplicate profile values
  with invalid fields are rejected whether the invalid value appears first or
  last.
- Bindings one second inside and outside the 30-day retention boundary, and
  five seconds on either side, match. A same-second exact-cutoff run retained
  the binding in both releases and Modex.
- `bound_at` at signed 64-bit minimum and maximum is accepted with the same
  retention result; values outside the range, fractional numbers and exponent
  numbers are rejected by all three binaries.

After the fix, `make build`, the focused empty-identifier regression, all 69
Python session tests, native `test_sessions`, and the 71-file production
dependency audit passed. These selected comparisons do not establish full
state or security parity; locking and malformed-primary recovery remain open.
