# Empty profile-list slice on Prodex 0.166.0

The verified active 0.166.0 Linux x86-64 oracle returns the exact empty-profile
panel when `HOME/.prodex` is absent. Modex now matches its output and exit code
for that case. Modex checks the app-root directory entry without creating it,
so it leaves the isolated home untouched. The reference creates profile
lifecycle and update-check locks, and may leave runtime-housekeeping files
asynchronously. Those side effects remain unmatched.

`tests/test_profile_list_empty_01660.py` runs each real process in a fresh
Bubblewrap namespace with synthetic HOME, cleared environment, isolated `/tmp`,
and no credentials or provider traffic. It checks the exact reference panel,
the guaranteed lifecycle and update lock files, and that every observed path
is either required or an allowed asynchronous housekeeping path. It compares
the Modex output, exit code and empty side-effect set with that result. The
oracle is pinned by the SHA-256 recorded in `test_active_baseline_01660.py`.

The same active-release module verifies that malformed state and a dangling
root symlink with a trailing slash do not produce the empty panel. It also
checks a dangling ancestor symlink; Modex treats only a missing final entry
under an existing resolved directory as absence. Other lookup failures stay
fail-closed.

Reproduce from the repository root with Mojo 1.2.0:

```sh
make BUILD_DIR=/tmp/modex-profile-gap-build build
MODEX_BINARY=/tmp/modex-profile-gap-build/modex \
  PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
  PYTHONPATH=tests python3 -m unittest -v test_profile_list_empty_01660
python3 scripts/ci/check-product-dependencies.py
git diff --check
```

This Linux x86-64 slice does not qualify the other five release targets or
implement populated profile listing, state recovery, locking, or Guardian
behavior. Keep the full `PROFILE-LIST` contract unpromoted.
