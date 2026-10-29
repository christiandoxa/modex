# Repeated Super launch with shared history

On Linux x86-64, the real-process test
`test_super_launch_01651.ActiveSuperLaunchTests.test_repeat_launch_with_shared_history_documents_current_gap`
starts two sequential DeepSeek Super commands using the same isolated home,
synthetic Codex child, synthetic API key, and loopback upstream. The first child
writes a synthetic session and exits 7; the fixture appends a synthetic history
record before the second launch. Both checksum-pinned Prodex 0.165.1 and
0.439.2 launch the child twice and return 7 twice. Modex launches it once,
then returns 1 with `Super clean-home launch cannot reconcile existing Codex
data yet`. No upstream request is sent; the session and history record remain
present and overlays are cleaned up in all three cases. The passing test
records a mismatch, not a parity pass.

At 0.165.1 commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`,
`crates/prodex-optional-tools/src/launch_home.rs` links shared history,
sessions, archived sessions and attachments into the overlay, creating missing
paths without truncating existing history. The same file is identical at the
0.439.2 pin `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.
`crates/prodex-app/src/app_commands/child_process.rs` holds a shared session
maintenance lock during child execution, while
`crates/prodex-shared-codex-fs/src/lib.rs` uses an exclusive lock for
maintenance. Modex's `_clean_home` currently rejects the shared files before
launch and its clean-home setup would otherwise open `history.jsonl` for
truncating write. Simply allowing the files without changing setup and
coordinating maintenance would risk data loss and concurrency errors.

The focused test passed with both pinned release binaries and Modex using
synthetic isolated fixtures. This observation covers one sequential clean-home
case, not concurrent launches, session maintenance, recovery, security, or any
other release target. Existing shared Codex and managed-profile lifecycle
remain unimplemented.
