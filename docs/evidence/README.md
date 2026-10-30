# Evidence path sanitization

The current tree generalizes machine-specific user-home components in archived evidence and test expectations to `/home/test-user` where they appear. Expectations tied to synthetic fixture directories retain those fixture paths. Super hook oracle snapshots mark `cases[*].argv[0]` as `<SANITIZED_ORACLE_EXECUTABLE>` and record that field in `sanitized_fields`. These changes affect path text only; baseline commits, oracle digests, versions, measured results, timings, and checksum-protected corpus fixtures remain unchanged. Anonymous temporary paths are retained.
