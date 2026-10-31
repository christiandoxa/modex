# Hidden sub-agent helper help

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.1 as active describe the original capture.

Prodex 0.166.1 exposes `__sub-agent-exec` help in its active CLI inventory.
The checksum-pinned oracle prints the captured
`help/__sub-agent-exec.txt` contents for direct `--help`, direct `-h`, and
`help __sub-agent-exec`, with exit 0 and no filesystem mutations.

Modex now serves those three production help routes with the same usage and
option text, substituting the invoked executable name. The child-launch helper
itself remains unimplemented; this slice covers help output only.

Validation used Mojo `1.2.0 (2016d0cd)`: `make build
BUILD_DIR=/tmp/modex-01661-gap-build` passed, and
`test_sub_agent_exec_help_01661.py` passed all three real-process comparisons.
The test uses an isolated home and workspace with the official 0.166.1 Linux
oracle and confirms neither process creates state.
