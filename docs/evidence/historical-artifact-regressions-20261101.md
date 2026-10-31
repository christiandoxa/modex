# Historical artifact regressions on 2026-11-01

The active parity target remains Prodex 0.166.2. These are historical
regressions, not 0.166.2 acceptance evidence.

Official Prodex workflow artifacts were recovered outside the repository and
their Linux executables matched the existing pinned SHA-256 values. The
0.439.2 source snapshot also passed exact-commit verification.

| Release | Workflow run | Artifact ID | Executable SHA-256 | Artifact expiry (UTC) |
| --- | --- | --- | --- | --- |
| 0.439.2 | [40300566491](https://github.com/christiandoxa/prodex/actions/runs/40300566491) | 12641885680 | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` | 2026-11-02 09:54:42 |
| 0.439.5 | [40533648780](https://github.com/christiandoxa/prodex/actions/runs/40533648780) | 12746283923 | `96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5` | 2026-11-03 15:46:30 |

The isolated 0.439.5 lane passed all three test methods. In the cross-release
lane, five non-session methods passed inside a Bubblewrap network namespace.
The remaining session methods failed to create nested namespaces there, then
passed all five methods with synthetic HOME/XDG/TMP and each application
process isolated in its own Bubblewrap namespace. Thus all ten methods passed
across separate invocations; the combined lane did not pass in one invocation.
One session test deliberately records a baseline panic and safer Modex behavior,
so this is not a claim that every behavior is identical.

The release assets and tags remain unavailable through their normal public
release endpoints. Anonymous artifact ZIP download returned HTTP 401, and the
workflow artifacts expire, so this recovery does not provide a demonstrated
durable credential-free hosted CI source. Required historical gates remain
fail-closed. No binary was added to the repository.
