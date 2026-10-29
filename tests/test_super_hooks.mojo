"""Native checks for frozen hook-trust selection and JSON-RPC sequencing."""

from std.testing import assert_equal, assert_true

from modex.json import JsonDocument
from modex.super_hooks import HookTrustSession, _i64, hook_trust_updates, verify_hooks_trusted


def expect_error(mut session: HookTrustSession, line: String, expected: String) raises:
    var rejected = False
    try:
        _ = session.accept(line)
    except error:
        rejected = True
        assert_equal(String(error), expected)
    assert_true(rejected)


def main() raises:
    var session = HookTrustSession("/synthetic/雪\"workspace")
    assert_equal(session.request(), '{"id":1,"jsonrpc":"2.0","method":"initialize","params":{"capabilities":{"experimentalApi":true},"clientInfo":{"name":"prodex-hook-trust","version":"0.439.2"}}}')
    for ignored in ["bad", "{}", '{"id":"1","result":{}}', '{"id":1.0,"result":{}}', '{"id":1e0,"result":{}}', '{"id":2,"result":{}}', '{"method":"notice"}']:
        assert_true(not session.accept(ignored))
        assert_equal(session.phase, 1)
    assert_true(session.accept('{"id":1,"result":null}'))
    assert_equal(session.request(), '{"id":2,"jsonrpc":"2.0","method":"hooks/list","params":{"cwds":["/synthetic/雪\\\"workspace"]}}')
    assert_true(session.accept('{"id":2,"result":{"data":[{"hooks":[{"key":"z","currentHash":"first","trustStatus":"untrusted"},{"key":"a","currentHash":"hash:a","trustStatus":"modified"},{"trustStatus":"Untrusted"},{"key":"z","currentHash":"last","trustStatus":"modified"}]}]}}'))
    assert_equal(session.phase, 3)
    assert_equal(session.updates, '{"a":{"trusted_hash":"hash:a"},"z":{"trusted_hash":"last"}}')
    assert_true('"keyPath":"hooks.state"' in session.request())
    assert_true('"reloadUserConfig":true' in session.request())
    assert_true(session.accept('{"id":3,"result":{"status":"okOverridden"}}'))
    assert_equal(session.phase, 4)
    assert_true(session.accept('{"id":4,"result":{"data":[{"hooks":[{"trustStatus":"trusted"},{"trustStatus":"unknown"}]}]}}'))
    assert_true(session.done and not session.legacy)

    var no_updates = HookTrustSession("/synthetic")
    _ = no_updates.accept('{"id":1,"result":{}}')
    _ = no_updates.accept('{"id":2,"result":{"data":[]}}')
    assert_equal(no_updates.phase, 4)
    _ = no_updates.accept('{"id":4,"result":{"data":[]}}')
    assert_true(no_updates.done)
    for phase in [2, 3]:
        var legacy = HookTrustSession("/synthetic")
        legacy.phase = phase
        _ = legacy.accept('{"id":' + String(phase) + ',"error":{"code":-32601}}')
        assert_true(legacy.done and legacy.legacy)
    for phase in [1, 4]:
        var rejected_legacy = HookTrustSession("/synthetic")
        rejected_legacy.phase = phase
        expect_error(rejected_legacy, '{"id":' + String(phase) + ',"error":{"code":-32601,"message":"missing"}}', "Codex hook-trust " + rejected_legacy.operation() + " failed (-32601): missing")

    var failures = HookTrustSession("/synthetic")
    expect_error(failures, '{"id":1,"error":null,"result":{}}', "Codex hook-trust initialize failed (0): unknown JSON-RPC error")
    expect_error(failures, '{"id":1}', "Codex hook-trust response omitted result")
    expect_error(failures, '{"id":1,"error":{"code":-32601.0,"message":""}}', "Codex hook-trust initialize failed (0): ")
    failures.phase = 2
    expect_error(failures, '{"id":2,"result":{"data":[{}, {"warnings":[false,"warning",3,"later"]}]}}', "Codex hooks/list reported warnings: warning; later")
    expect_error(failures, '{"id":2,"result":{"data":[{"hooks":[],"errors":[""]}]}}', "Codex hooks/list reported errors: ")
    expect_error(failures, '{"id":2,"result":null}', "Codex hooks/list response omitted data")
    expect_error(failures, '{"id":2,"result":{"data":[{}]}}', "Codex hooks/list entry omitted hooks")
    expect_error(failures, '{"id":2,"result":{"data":[{"hooks":[{"trustStatus":"modified"}]}]}}', "Codex hooks/list returned a trustable hook without key")
    expect_error(failures, '{"id":2,"result":{"data":[{"hooks":[{"trustStatus":"modified","key":" "}]}]}}', "Codex hooks/list returned a trustable hook without currentHash")
    failures.phase = 3
    expect_error(failures, '{"id":3,"result":{"status":"Ok"}}', "Codex hook-trust config write did not report a successful status: Ok")
    expect_error(failures, '{"id":3,"result":{"status":null}}', "Codex hook-trust config write did not report a successful status: <missing>")
    failures.phase = 4
    expect_error(failures, '{"id":4,"result":{"data":[{"hooks":[{"trustStatus":"modified"}]}]}}', "Codex hook remained untrusted after Super preflight: <unknown>")

    var whitespace = JsonDocument('{"data":[{"hooks":[{"key":" ","currentHash":" ","trustStatus":"untrusted"}]}]}')
    assert_equal(hook_trust_updates(whitespace, whitespace.root), '{" ":{"trusted_hash":" "}}')
    for integer in ["9223372036854775807", "-9223372036854775808", "0"]:
        var doc = JsonDocument(integer)
        assert_true(_i64(doc, doc.root))
    for non_i64 in ["-0", "1.0", "1e0", "9223372036854775808", "-9223372036854775809", '"1"', "null"]:
        var doc = JsonDocument(non_i64)
        assert_true(not _i64(doc, doc.root))

    var boundary = JsonDocument('{"data":[{"hooks":[{"trustStatus":"' + String("x") * 65536 + '"}]}]}')
    assert_equal(hook_trust_updates(boundary, boundary.root), "{}")
    failures.phase = 2
    expect_error(failures, '{"id":2,"result":{"data":[{"hooks":[{"trustStatus":"' + String("x") * 65537 + '"}]}]}}', "compiled Mojo hook trust selection rejected oversized input")
    var many = String("null,") * 65535 + "null"
    var hook_boundary = JsonDocument('{"data":[{"hooks":[' + many + ']}]}')
    verify_hooks_trusted(hook_boundary, hook_boundary.root)
    expect_error(failures, '{"id":2,"result":{"data":[{"hooks":[' + many + ',null]}]}}', "compiled Mojo hook trust selection rejected oversized input")
    failures.phase = 3
    expect_error(failures, '{"id":3,"result":{"status":"' + String("x") * 65537 + '"}}', "compiled Mojo hook config-write classification rejected oversized input")
    print("Super hook-trust protocol checks: PASS")
