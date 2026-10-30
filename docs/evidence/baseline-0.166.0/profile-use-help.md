# Top-level profile use help

The top-level `use` command now exposes selected help and parser diagnostics
from the verified Prodex 0.166.0 Linux release. The active process test covers
long and short help, `help use`, a custom executable name, and selected
invalid-argument and help-order cases with isolated synthetic homes. It also
checks that stateful `use` requests remain guarded without creating state.

These checks qualify only the listed CLI cases. Profile selection, lifecycle
locking and recovery, and other release targets remain unimplemented or
unverified.
