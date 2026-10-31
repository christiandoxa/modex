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

An additional synthetic comparison found an unresolved semantic precedence
mismatch. With `ping openai --base-url ftp://example.test/v1 --model ''`,
Prodex 0.166.2 exits 1 with
`Error: ping upstream base URL must be an http(s) URL with host and no credentials, query, or fragment`,
while Modex exits 1 with
`Error: --model must be nonempty and contain no control characters`. Both
processes leave the isolated home untouched. The pinned oracle is the
checksum-verified 0.166.2 binary described above; no production change was
retained because Mojo 1.2.0's standard library provides no URL or UTS #46 IDNA
parser, and hand-parsing has security and compatibility edge cases.
`test_base_url_precedence_mismatch_and_valid_url_control_are_visible` records
this mismatch and a valid-URL control against the pinned binary; both use an
empty model, so neither invokes provider code.

Probe constraints for any future implementation: Reqwest accepts empty
userinfo markers (`https://@example.test/` and `https://:@example.test/`) but
rejects nonempty credentials, including `https://@user@example.test/`.
Invalid IPv4 and IDNA hosts are diagnosed before credential-policy errors.
IDNA probes rejected U+200E LRM, U+202A bidi embedding, U+E000 private-use,
U+FDD0 noncharacter, U+E0001 tag, U+0080 C1 control, and U+200C joiner scalars
in host labels. Prodex also normalizes special schemes such as `http:///v1`
before validation, trims surrounding C0/space, and removes TAB from URLs.
These cases are not covered by the existing ping differential test, and no
full URL parity claim is made. The ping operation remains guarded; valid-looking
arguments reach the existing guard without a provider request or state change.
