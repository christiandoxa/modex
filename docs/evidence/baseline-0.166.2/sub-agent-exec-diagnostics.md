# Hidden sub-agent argument diagnostics against Prodex 0.166.2

Prodex 0.166.2 is the active, version-pinned compatibility oracle. This
focused check does not establish contract parity.

The official 0.166.2 tag resolves to commit
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. The downloaded x86-64 Linux
oracle matches its official `SHA256SUMS` entry:

- `SHA256SUMS`: `acb1e7735cf36c8b5fef49e2f33f52f9def5ec4e1c021cd038eebeabe32f4731`
- `prodex-x86_64-unknown-linux-gnu`:
  `e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`

`tests/test_sub_agent_exec_diagnostics_01662.py` compares isolated real
processes for missing required options, missing values, duplicate options,
unknown options (including the `--config` suggestion), positionals, `--`, empty
option values, and left-to-right short-help clusters. Additional cases confirm
that explicit empty values on repeated `--config` and `--task-file` options
report duplicates, and malformed `--help=value` following a pending path value
retains the release's error precedence and usage. Six more cases compare
pending split values followed by attached `--config=value` or
`--task-file=value` options, plus malformed help after an accepted attached
task-file value and an attached-config usage control. These preserve the
release's missing-value diagnostic and grouped help usage; accepted split
values keep their existing usage form.
Malformed arguments produce the release's exit-2 diagnostics without creating
state in either isolated home. Syntactically valid arguments still stop at
Modex's existing execution guard; delegated sub-agent execution remains
unimplemented.

Verification on Linux x86-64: the Mojo 1.2.0 (2016d0cd) production build
and the focused differential and help regression tests passed with the
checksum-verified oracle and isolated synthetic homes. The active fast and full
CI suites already include `tests/test_sub_agent_exec_diagnostics_01662.py`.
