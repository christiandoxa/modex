# Unicode reference data

These nine files are unmodified Unicode 17.0 reference data and independent
test inputs for the frozen `unicode-width` 0.2.2 behavior. Their combined size
is 1,992,045 bytes. SHA-256 checksums are in [SHA256SUMS](SHA256SUMS).
Production does not read these files, and the build does not run a data or code
generator. Production interval tables are authored in Mojo; no external width
implementation code is copied.

The Unicode Character Database files come from
[Unicode 17.0.0 UCD](https://www.unicode.org/Public/17.0.0/ucd/):

- `EastAsianWidth.txt`
- `DerivedCoreProperties.txt`
- `ArabicShaping.txt`
- `HangulSyllableType.txt`
- `auxiliary/GraphemeBreakProperty.txt`
- `extracted/DerivedJoiningType.txt`
- `emoji/emoji-data.txt`
- `emoji/emoji-variation-sequences.txt`

`emoji-zwj-sequences.txt` comes from the
[Emoji 17.0 data](https://www.unicode.org/Public/17.0.0/emoji/emoji-zwj-sequences.txt).

Copyright 2025 Unicode, Inc. See [Unicode License V3](../../../LICENSES/Unicode-3.0.txt).
The distribution must include the Unicode license notice in `NOTICE` and the
full license in `LICENSES/Unicode-3.0.txt` alongside Unicode-derived data.
