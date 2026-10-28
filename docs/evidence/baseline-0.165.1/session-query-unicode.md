# Session-query Unicode casing against 0.165.1

The release source normalizes session queries and fields with Rust's
`str::to_lowercase`. Its pinned Rust 1.99.1 toolchain uses Unicode 17 properties
for contextual Greek sigma. Modex previously recognized only a few combining
marks and apostrophes, so a query such as `aσ.a` failed to match `AΣ.A`; the
0.165.1 process matched it. The same discrepancy appeared across a zero-width
joiner and a modifier letter.

The production selector now checks the Unicode 17 Cased and Case_Ignorable
properties. The checked-in property data comes from the existing checksum-pinned
Unicode fixture; no test fixture or generator is needed by the product build.
`tests/test_unicode_case_properties.py` compares both properties for all Unicode
scalar values against that data, and the native audit
`mojo run -I src -D ASSERT=all tests/unicode_properties_derive.mojo` does the
same. `tests/test_session_query_01651.py` compares eight production query cases
against the checksum-verified release in isolated homes, including positive and
negative controls. All passed on Linux x86-64.

This does not prove every Unicode lowercase mapping or the complete session
contract; other state, storage and platform gaps remain open.
