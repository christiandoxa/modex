# Active 0.166.0 session-query contextual sigma regression

Prodex 0.166.0 is pinned at `9f69e1835808f478f59f12a3ae3fa88027d896a4`;
the active Linux oracle SHA-256 is pinned in
`tests/test_active_baseline_01660.py`. The source path
`crates/prodex-session-store/src/lib.rs::session_report_matches_query`
lowercases the query and searchable fields before calling the compiled
substring matcher. Modex uses `session_query_lowercase` on the production
`session list --query` path.

`ActiveBaseline01660Tests.test_session_query_case_ignorable_sigma_matches_active_release`
reads the checksum-pinned Unicode 17 `DerivedCoreProperties.txt` fixture and
builds one synthetic session title containing all 2,794 `Case_Ignorable`
scalars between Greek capital sigma and a following cased letter. A lowercase
query uses the expected non-final sigma for every segment. The test runs the
real release and Modex processes in separate isolated homes and workspaces;
both return only the synthetic session ID, with no stderr, and neither changes
the fixture file. This covers the contextual-sigma skip condition through the
connected CLI path without printing titles or touching managed state.

Reproduce after building Modex with Mojo 1.2.0 and setting `PRODEX_ORACLE` to
the verified 0.166.0 Linux binary:

```sh
MODEX_BINARY=build/modex \
PYTHONPATH=tests python3 -m unittest \
  test_active_baseline_01660.ActiveBaseline01660Tests.test_session_query_case_ignorable_sigma_matches_active_release -v
```

This is one aggregate query regression on Linux x86-64. It does not qualify
managed-state filters, all Unicode lowercase mappings, other targets, or
overall session parity. It changes tests and evidence only; no production
behavior or parity status is promoted.
