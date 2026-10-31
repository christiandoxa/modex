# Historical oracle recovery from official workflow artifacts

Prodex 0.166.0 remains the active target. The following recovered binaries are
only for historical regression tests; they do not establish 0.166.0 parity.

The official `christiandoxa/prodex` Actions API reports these successful
standalone release runs and retained `x86_64-unknown-linux-gnu` artifacts:

| Historical release | Pinned source commit | Run | Artifact | Verified binary SHA-256 |
| --- | --- | --- | --- | --- |
| 0.439.2 | `72b77478a5198fc5da6b4d2253137f9cdbf43be9` | `40300566491` | `12641885680` | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` |
| 0.439.5 | `ac9aad08f25d6dc8cda96463ce2045b40f35f510` | `40533648780` | `12746283923` | `96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5` |

Both downloaded `prodex` files matched the independently pinned binary
digests already recorded in the baseline evidence. The existing reference
helper accepted them through the versioned `PRODEX_ORACLE_04392` and
`PRODEX_ORACLE_04395` overrides. The historical `test_session_04395_slice`
module then passed both tests with isolated synthetic state; one test records
an intentional safer Modex behavior, not a parity pass. No binary was added
to the repository.

The artifact download API returned HTTP 401 without authentication. The
successful downloads used an authenticated read of the official workflow
artifacts; a clean hosted Modex runner has not been shown to have access to
them. Artifacts can expire. Until an authorized, available source supplies
the exact pinned bytes, hosted historical lanes remain blocked and CI fails
closed. Do not treat an unavailable artifact or a substituted build as a pass.
