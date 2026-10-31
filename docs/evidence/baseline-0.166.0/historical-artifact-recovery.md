# Historical oracle recovery from official workflow artifacts

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Prodex 0.166.2 is the active target. The following recovered binaries are
only for historical regression tests; they do not establish 0.166.2 parity.

The official `christiandoxa/prodex` Actions API reports these successful
standalone release runs and retained `x86_64-unknown-linux-gnu` artifacts:

| Historical release | Pinned source commit | Run | Artifact | Verified binary SHA-256 |
| --- | --- | --- | --- | --- |
| 0.439.2 | `72b77478a5198fc5da6b4d2253137f9cdbf43be9` | `40300566491` | `12641885680` | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` |
| 0.439.5 | `ac9aad08f25d6dc8cda96463ce2045b40f35f510` | `40533648780` | `12746283923` | `96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5` |

Both downloaded `prodex` files matched the independently pinned binary
digests already recorded in the baseline evidence. The existing reference
helper accepted them through the versioned `PRODEX_ORACLE_04392` and
`PRODEX_ORACLE_04395` overrides. The historical 0.439.2 CLI module passed 13
tests, the 0.439.5 provider catalog module passed one test, and
`test_session_04395_slice` passed two tests with isolated synthetic state;
one session test records an intentional safer Modex behavior, not a parity
pass. No binary was added to the repository.

To recover the same artifacts using an authenticated GitHub CLI, first set
`MODEX_HISTORICAL_ORACLES` to a private directory outside the repository, then
run the following. The reference helper checks each binary against its
existing pinned digest before it can be used as an oracle.

```sh
set -eu
: "${MODEX_HISTORICAL_ORACLES:?Set a private directory outside the repository}"
mkdir -p "$MODEX_HISTORICAL_ORACLES/0.439.2" "$MODEX_HISTORICAL_ORACLES/0.439.5"
gh run download 40300566491 --repo christiandoxa/prodex \
  --name x86_64-unknown-linux-gnu --dir "$MODEX_HISTORICAL_ORACLES/0.439.2"
gh run download 40533648780 --repo christiandoxa/prodex \
  --name x86_64-unknown-linux-gnu --dir "$MODEX_HISTORICAL_ORACLES/0.439.5"
export PRODEX_ORACLE_04392="$MODEX_HISTORICAL_ORACLES/0.439.2/prodex"
export PRODEX_ORACLE_04395="$MODEX_HISTORICAL_ORACLES/0.439.5/prodex"
python3 scripts/ci/reference.py oracle 0.439.2
python3 scripts/ci/reference.py oracle 0.439.5
chmod 755 "$PRODEX_ORACLE_04392" "$PRODEX_ORACLE_04395"
```

The artifact download API returned HTTP 401 without authentication. The
successful downloads used an authenticated read of the official workflow
artifacts; a clean hosted Modex runner has not been shown to have access to
them. The repository's workflow policy currently forbids `secrets.` references,
so these credentials cannot be added to CI without changing that policy.
Artifacts can expire. Until an authorized, available source supplies
the exact pinned bytes, hosted historical lanes remain blocked and CI fails
closed. Do not treat an unavailable artifact or a substituted build as a pass.
