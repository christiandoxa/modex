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
unsupported `--base-url` scheme. Modex now checks URL scheme and authority
policy after option syntax and before model validation. Split and attached FTP
URLs match Prodex 0.166.2. Empty, missing, and malformed schemes also match,
including Prodex's `: relative URL without a base` detail. Empty hosts return
`: empty host`; malformed, negative, and out-of-range ports return
`: invalid port number`. Nonempty credentials, query, and fragment URLs return
Prodex's generic base-URL error. Empty userinfo markers and empty ports remain
accepted. Surrounding C0/space and CR/LF, embedded CR/LF scheme controls, TAB
removal, backslash and slash normalization, and special-scheme controls match
the oracle. CR/LF embedded in a host is removed by URL preprocessing, while
CR/LF in the scheme keeps the generic base-URL diagnostic. Malformed bracketed
IPv6 literals return `invalid IPv6 address`. Host diagnostics also take
precedence over malformed ports: malformed IPv6, IDNA, and IPv4 hosts retain
their host-specific errors, while a valid IPv6 host with a malformed or
out-of-range port returns `invalid port number`. Valid ASCII, IPv4, IPv6, and
`bücher.example` controls reach model validation.
`test_base_url_scheme_precedence_matches_release_without_mutation` and
`test_base_url_host_port_and_policy_precedence_matches_release` cover these
cases in isolated homes; the operation remains guarded and makes no provider
request.

On 2026-10-31, `rtk make build` and all 11 methods in
`PYTHONPATH=tests rtk python3 -m unittest test_ping_diagnostics_01662 -v`
passed on Linux x86-64. The differential suite used the checksum-verified
Prodex 0.166.2 oracle (SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`); each
process ran with an isolated synthetic home and no provider traffic. These
results cover only the listed offline ping diagnostics and do not establish
full URL, IDNA, ping operation, or cross-target parity.

The validator reuses Modex's authority checks but does not implement full
WHATWG URL or UTS #46 processing. Known remaining IDNA mismatches are recorded
in `test_unimplemented_uts46_host_validation_remains_visible`: Prodex rejects
LRM, bidi, private-use, noncharacter, tag, C1, and joiner host probes before
model validation, while Modex reaches the model error. This does not establish
full host or IDNA parity. The ping operation remains guarded and makes no
provider request.

Probe constraints for any future implementation: Reqwest accepts empty
userinfo markers (`https://@example.test/` and `https://:@example.test/`) but
rejects nonempty credentials, including `https://@user@example.test/`.
Invalid IPv4 and IDNA hosts are diagnosed before credential-policy errors.
IDNA probes rejected U+200E LRM, U+202A bidi embedding, U+E000 private-use,
U+FDD0 noncharacter, U+E0001 tag, U+0080 C1 control, and U+200C joiner scalars
in host labels. Empty-userinfo markers and common host/port errors are covered
by the focused differential tests; the UTS #46 scalar probes remain visible
mismatches. Prodex trims surrounding C0/space and removes TAB from URLs; the
tested preprocessing controls match, while full URL parity remains unverified.
The ping operation remains guarded; valid-looking arguments reach the existing
guard without a provider request or state change.
