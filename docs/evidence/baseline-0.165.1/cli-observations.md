# Selected 0.165.1 CLI observations

The official Linux x86-64 artifact is pinned in `reference-verification.json`.
On Mojo 1.2.0 (2016d0cd), `tests/test_cli_01651.py` compared the production
Modex binary with that artifact using isolated homes, empty PATH, and no real
credentials. Leading `--version` and `-V` with six different tails produced
the respective product identities and no home mutations. Five root-help forms
and a custom executable name matched after the documented identity mapping;
the isolated homes stayed unchanged. These comparisons passed on 2026-10-29.

These observations do not cover all command-line parsing, installation,
security, startup paths, or any non-Linux target; they do not establish full
contract or release parity.

The read-only `update --help`, `update -h`, `help update`, and tested trailing
argument forms now match 0.165.1 after executable-name mapping, with no home
mutations. Update execution itself remains unimplemented.

The `update` argument parser now matches selected 0.165.1 help, invalid option,
positional, literal separator, attached value and custom-executable cases. The
isolated comparisons verify exit status, stdout, stderr and no home mutations.
Bare update still fails closed; update execution and untested combinations are
not qualified.

For `help update`, three unknown subcommands containing `=` now retain the
whole argument in the diagnostic, matching the 0.165.1 executable and the
historical 0.439.2 executable. The isolated checks compare exit status, output,
and home mutations; they do not qualify other argument combinations.
