# Session-query lowercase slice

Prodex 0.439.2 commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`
lowercases query text and searchable fields before matching. Tests execute
the verified Linux oracle SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
and Modex with synthetic session files and isolated homes.

The selected comparisons cover dotted-capital-I expansion in both the query
and provider name, ordinary non-ASCII casing, final and non-final Greek
sigma, and common combining marks before or after sigma. A separate test
rechecks selected cases against the independently verified historical
0.439.5 oracle. Before the change, the active 0.439.2 test reproduced the
dotted-I and final-sigma mismatches. The production CLI and native tests pass
for the selected cases after the change. Context scanning uses iterators rather
than allocating an integer array for each field; a native control includes a
1 MiB title followed by sigma.

The implementation does not cover the full Unicode Case_Ignorable property
used by contextual sigma rules. This is partial evidence and does not alter
the session contract's FAIL status or the six-platform denominator.
