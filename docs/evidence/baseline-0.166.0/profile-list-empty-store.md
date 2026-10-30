# Empty profile list gap on Prodex 0.166.0

The verified active 0.166.0 Linux x86-64 oracle returns the “No profiles
configured” panel when `HOME/.prodex` is absent. It creates the profile
lifecycle and update-check locks. It also starts runtime-housekeeping work that
may leave its marker and lock asynchronously. Modex currently returns its
unimplemented-command error and leaves the home untouched. This is a
characterized gap, not profile-list parity.

`tests/test_profile_list_empty_01660.py` runs each real process in a fresh
Bubblewrap namespace with synthetic HOME, cleared environment, isolated `/tmp`,
and no credentials or provider traffic. It checks the exact reference panel,
the guaranteed lifecycle and update lock files, and that every observed path
is either required or an allowed asynchronous housekeeping path. It also checks
the Modex error and absence of Modex side effects. The oracle is pinned by the
SHA-256 recorded in `test_active_baseline_01660.py`.

Reproduce from the repository root with Mojo 1.2.0:

```sh
make BUILD_DIR=/tmp/modex-profile-gap-build build
MODEX_BINARY=/tmp/modex-profile-gap-build/modex \
  PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
  PYTHONPATH=tests python3 -m unittest -v test_profile_list_empty_01660
python3 scripts/ci/check-product-dependencies.py
git diff --check
```

This single Linux x86-64 process case does not qualify the other five release
targets or implement populated profile listing, state recovery, locking, or
Guardian behavior.
