# TOML conformance data

Unmodified test inputs and expected typed JSON values from
[toml-lang/toml-test](https://github.com/toml-lang/toml-test), pinned at commit
`ff49d109861c1ad25af53f687f2aef19ab650600`. Only non-executable fixture data,
version manifests and the MIT license are retained; no upstream implementation,
runner or generator is included.

`files-toml-1.1.0` selects the target-version cases. Other fixtures remain
available for explicit legacy/version-transition regressions. Checksums of
the imported files are recorded in `SHA256SUMS`.

These files are independent test inputs only. The production parser is native
Mojo and its build/runtime does not load or generate code from this directory.
See [LICENSE](LICENSE) for the upstream data license.
