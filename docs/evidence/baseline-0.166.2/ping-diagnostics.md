# Offline ping group diagnostics

The checksum-verified Prodex 0.166.2 Linux oracle and the production Modex
binary were compared with isolated synthetic homes and no provider traffic.
For `ping` without a subcommand (including a trailing `--`), both now print the
same group help to stderr and exit 2. Unknown long and short flags and unrecognized subcommands (including
suggestion and `--` cases) produce the same error, usage, and exit status. Neither process created state in the test.

The first differential sweep had missed truncated long help flags. Modex now
matches the release for `ping --h`, `--h=value`, `--he`, `--hel`, and `--hlp`,
including the `--help` suggestion and its `ping --help <COMMAND>` usage.
`ping openai` now emits the same suggestion and usage for those forms, while
keeping previously accepted options in usage and reporting syntax errors
before model-value validation. Negative controls such as `--z` still receive
no suggestion. All comparisons use isolated synthetic homes and leave them
unchanged.

For `ping openai`, first unknown options and positional arguments also match;
missing values for `--profile`/`-p`, `--model`, `--effort`, and `--base-url`
match, as do duplicate value options and duplicate `--json`/`--no-proxy` flags.
These parse errors exit 2 without creating files. Valid `ping openai` invocations
remain behind Modex's unimplemented-operation guard and make no provider request.
`tests/test_ping_diagnostics_01662.py` covers these cases against the pinned
oracle. The existing 0.166.0 ping help regression also passed. This does not
implement `ping openai`, validate other argument combinations, or establish
full ping parity.

Arguments after `--` are reported literally, including values such as
`--foo=x`. After option syntax succeeds, empty and whitespace-only `--model`
values and C0, DEL, or C1 control characters return Prodex's
`Error: --model must be nonempty and contain no control characters` with exit
1. Help and option-syntax errors keep their earlier precedence. Nonempty model
values without control characters still reach Modex's guarded operation error;
the operation remains unimplemented and no provider request or state change is
made. `tests/test_ping_diagnostics_01662.py` covers both boundaries against the
pinned oracle.

An isolated synthetic differential exposed a precedence mismatch for an
unsupported `--base-url` scheme. Modex now checks the base URL after option
syntax and before model validation. Split and attached FTP URLs match Prodex
0.166.2. Empty, missing, and malformed schemes also match, including Prodex's
`: relative URL without a base` detail. The checker trims surrounding C0/space
and removes TAB before scheme classification. Differential controls cover
surrounding CR/LF, embedded CR/LF in the HTTPS scheme, a removable TAB in the
HTTPS scheme, and special-scheme normalization of `http:///v1`; these match the
oracle and leave synthetic homes untouched. The operation remains guarded and
no provider request is made.

This is not full URL validation. With an invalid model, Prodex reports
`: empty host` for `https://` and `https://?x`, and `: invalid port number` for
`https://example.test:abc/v1`; Modex reaches model validation. Prodex also
rejects credential, query, and fragment URLs before model validation, while
Modex reaches model validation. The differential test records these mismatches
in `test_unimplemented_url_validation_mismatches_remain_visible`. Mojo 1.2.0's
standard library has no URL or UTS #46 IDNA parser, so no full URL, host,
credential, query, fragment, or IDNA parity is claimed.

Probe constraints for any future implementation: Reqwest accepts empty
userinfo markers (`https://@example.test/` and `https://:@example.test/`) but
rejects nonempty credentials, including `https://@user@example.test/`.
Invalid IPv4 and IDNA hosts are diagnosed before credential-policy errors.
IDNA probes rejected U+200E LRM, U+202A bidi embedding, U+E000 private-use,
U+FDD0 noncharacter, U+E0001 tag, U+0080 C1 control, and U+200C joiner scalars
in host labels. Empty-userinfo, invalid host, and IDNA probes remain outside
the differential test. Prodex trims surrounding C0/space and removes TAB from
URLs; the tested preprocessing controls match, while full URL parity remains
unverified. The ping operation remains guarded; valid-looking arguments reach
the existing guard without a provider request or state change.
