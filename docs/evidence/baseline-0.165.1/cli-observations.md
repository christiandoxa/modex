# Selected 0.165.1 CLI observations

The official Linux x86-64 artifact is pinned in `reference-verification.json`.
On Mojo 1.2.0 (2016d0cd), `tests/test_cli_01651.py` compared the production
Modex binary with that artifact using isolated homes, empty PATH, and no real
credentials. Leading `--version` and `-V` with six different tails produced
the respective product identities and no home mutations. Five root-help forms
and a custom executable name matched after the documented identity mapping;
the isolated homes stayed unchanged. Two tests passed on 2026-10-29.

These observations do not cover all command-line parsing, installation,
security, startup paths, or any non-Linux target; they do not establish full
contract or release parity.
