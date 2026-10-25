from std.testing import assert_equal, assert_true

from modex.rtk_command import prefixed_noisy_command


def main() raises:
    for source in [String("cargo test"), "git -C /repo status", "printf 'a; b' && cargo test", "pwd||cargo test", "echo x", "claw-compactor benchmark", "  cargo check  ", "RUST_LOG=é　cargo　test", "'/usr/bin/cargo' test", "ca\\rgo test"]:
        var rewritten = prefixed_noisy_command(source)
        assert_true(rewritten)
        assert_equal(rewritten.value(), "rtk " + source)
    for source in [String(""), "cargo fmt", "git 'cargo test'", "rtk cargo test", "rtk", "ls.exe", "printf 'cargo test'", "git statusx"]:
        assert_true(not prefixed_noisy_command(source), source)
    var assignment = "CACHE=" + String("z") * 5000 + " cargo test"
    assert_equal(prefixed_noisy_command(assignment).value(), "rtk " + assignment)
    var large = "rg " + String("x") * (5 * 1024 * 1024)
    assert_equal(prefixed_noisy_command(large).value(), "rtk " + large)
    var oversized = String("x") * 4097 + " test"
    assert_true(not prefixed_noisy_command(oversized))
    var later = "rtk cargo test && cargo check"
    assert_equal(prefixed_noisy_command(later).value(), "rtk " + later)
    print("RTK command checks: PASS")
