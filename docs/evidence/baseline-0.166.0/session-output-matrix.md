# Session output comparisons

`tests/test_session_outputs_01660.py` runs the existing session-output fixture
against the checksum-verified Prodex 0.166.0 Linux binary and Modex. Selected
cases compare populated listings, filters, JSON metadata, archived children,
malformed records, Unicode and timestamp/timezone output. One inherited
non-object-record check exercises Modex alone and is not differential evidence.

The 14 test methods passed on Linux x86-64 in a private user, mount and network
namespace with isolated HOME and temporary storage, loopback only and no
default routes. The shared fixture normalizes temporary root paths and the
product name in resume commands. It checks output; it does not compare startup
locks or housekeeping, profile recovery, live session behavior, other targets,
or complete parity. Those gaps remain recorded in `docs/handoff.md`.
