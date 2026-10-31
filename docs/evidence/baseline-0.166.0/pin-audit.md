# Historical version pin audit

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

At the time of this audit the upstream target was Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Installed Prodex and Codex
versions depend on the host and can change independently of this target.
The official, checksum-verified 0.166.0 Linux test oracle is selected
separately and reports `prodex 0.166.0`. Modex's own product version remains
`modex 0.1.0-dev`; neither an installed version nor an oracle version alone
establishes parity.

The old selection was not caused by the installed executable: `AGENTS.md`,
`README.md`, `docs/baseline.json`, `docs/parity.json` and `docs/ci.md` named
0.439.2 as active. `tests/test_cli.py` defaulted generic `PRODEX_ORACLE` to
the 0.439.2 cache, while both CI scripts copied their active oracle and source
paths into `_04392` variables. The native hook initializer also sent version
0.439.2. These active pins and aliases have been corrected. The Makefile pins
Mojo 1.2.0, not a Prodex release; its version-suffixed native test names remain
historical tests.

`PRODEX_ORACLE` and `MODEX_REFERENCE_DIR` now identify the active release and
source in CI. Historical tests use versioned oracle variables, including
`PRODEX_ORACLE_01651`, `PRODEX_ORACLE_04392`, `PRODEX_ORACLE_04395`, and
`PRODEX_ORACLE_04390` where applicable. The helper validates each pinned hash;
`tests/test_ci_oracle_routing.py` checks that the paths are not aliased and
that missing required assets fail the run. Historical JSON fixtures, update
cache values, evidence, and version strings retain their original provenance;
they are not current-release acceptance evidence.

The 0.166.0 release manifest and SHA256SUMS identify six platform assets. Their
published digests match the GitHub asset metadata, but only the Linux x86-64
binary was downloaded and executed here. The inventory remains incomplete,
and all six platform qualifications remain open. See
`reference-verification.json` and `docs/parity.json`.
