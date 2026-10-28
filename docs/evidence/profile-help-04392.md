# Profile help against Prodex 0.439.2

The reference is the official Linux x86-64 binary for Prodex 0.439.2,
SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`,
from source commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.

The production CLI matches the reference's exit status, output bytes and lack
of filesystem changes for the tested profile group help forms, short and long
help for all seven subcommands, `help` aliases, a custom executable name and a
missing profile subcommand. Usage lines substitute Modex's executable name;
the release's example text is retained. Tests run each process with an isolated
HOME and synthetic filesystem.

Profile listing and mutations are still unimplemented. A clean-HOME control
records that the release lists an empty profile set and creates persistent lock
files, while Modex reports an unimplemented command without changing HOME.
For the tested unknown or malformed profile arguments, Modex's generic
unimplemented error differs from the release's parsing errors. Help after
earlier arguments has not been implemented.

Checks on the combined Linux x86-64 build:

- `make build` with Mojo 1.2.0 (2016d0cd) passed.
- `python3 scripts/ci/run-unittest.py test_profile_cli.py test_root_help.py`
  passed all nine methods without skips.
- `python3 scripts/ci/check-product-dependencies.py` passed for 71 Mojo files.

No stateful profile contract, platform obligation or release qualification is
promoted by these stateless help comparisons.
