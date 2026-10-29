# DeepSeek Flash request alias

The pinned 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
maps `flash` to `deepseek-flash` in `mojo/prodex_core/deepseek.mojo`; the frozen
0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` maps it to
`deepseek-v4-flash`. Previously Modex used the 0.439.2 value for direct `flash`
while already choosing the 0.165.1 value for combo retries. Both request paths
now use the 0.165.1 alias, including case-insensitive and trimmed forms.

`tests/test_provider_request_prepare.py` sends synthetic requests through the
real Super relay to a loopback upstream, compares both checksum-pinned releases,
and checks simple and non-simple request shapes. The test asserts the different
0.439.2 values explicitly and compares the rest of each body; explicit model
names and other combo candidates remain controls. Native request and simple
preparation checks plus model-fallback and credential-binding process controls
passed with Mojo 1.2.0. No real credentials or provider traffic were used.

The local `make test` run on `23bb0b18a3f5945e3d018b64d782cac8d704928f`
finished 1,036 tests with one failure: an older combo-model test expected the
0.439.2 alias for Modex despite the 0.165.1-targeted combo retry change. The
updated three-process test both records that release difference and covers the
separately observed direct-alias mismatch. The old full-run log remains at
`/tmp/modex-full-23bb0b1-20261030.log`, SHA-256
`5e72e9b6a3d931998b9cd56dc7616004b3e68a14371c3f1160f4141b95fdf6d8`.
The full suite has not been rerun on this change; the 0.439.2 alias difference,
other request shapes, non-host targets, and full provider parity remain open.
