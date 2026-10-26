from modex.runtime_recovery import NativeRecoveryRetry, recovery_retry_delay_ms, recovery_wire_action, recovery_plan, recovery_mutation_confirmed


def main() raises:
    for i in range(8):
        var expected = UInt64(0)
        if i > 0:
            expected = UInt64(60000) if i >= 5 else UInt64(5000) << UInt64(i - 1)
        assert recovery_retry_delay_ms(UInt32(i)) == expected
    var retry = NativeRecoveryRetry(0)
    assert retry.ready("root", 0, 1, 0)
    retry.completed_attempt(0)
    assert not retry.ready("root", 0, 2, 96000)
    assert not retry.ready("root", 0, 2, 100999)
    assert retry.ready("root", 0, 2, 101000)
    retry.completed_attempt(101000)
    assert retry.attempts == 2
    assert not retry.ready("root", 0, 3, 197000)
    assert retry.next_attempt_at == 207000
    assert retry.ready("root", 1, 3, 197000)
    assert retry.attempts == 0
    retry.completed_attempt(197000)
    assert not retry.ready("root", 1, 3, 201999)
    assert retry.ready("other", 0, 1, 0)
    retry.attempts = UInt32.MAX
    retry.completed_attempt(UInt64.MAX - 1)
    assert retry.attempts == UInt32.MAX
    assert retry.next_attempt_at == UInt64.MAX
    assert not retry.ready("other", 0, 2, UInt64.MAX - 1)
    assert retry.ready("other", 0, 2, UInt64.MAX)
    assert recovery_wire_action("active", "blocked", 1, 0, 0) == 0
    assert recovery_wire_action("systemError", "blocked", 1, 0, 0) == 2
    assert recovery_wire_action("idle", "paused", 1, 0, 0) == 1
    assert recovery_wire_action("idle", "", 0, 0, 0) == 3
    assert recovery_wire_action("idle", "", 32, 0, 0) == 1
    var session = String("00000000-0000-0000-0000-000000000001")
    var init = String('{"codexHome":"/synthetic/codex"}')
    var thread = String('{"thread":{"id":"') + session + '","sessionId":"' + session + '","ephemeral":false,"canAcceptDirectInput":true,"cwd":"/synthetic/work","status":{"type":"idle"}}}'
    assert recovery_plan(init, thread, '{"goal":null}', "/synthetic/codex", "/synthetic/work", session, False) == 3
    assert recovery_plan(init, thread, '{}', "/synthetic/codex", "/synthetic/work", session, False) == 0
    assert recovery_plan(init, thread, '{"goal":null}', "/wrong", "/synthetic/work", session, False) == 1
    assert recovery_plan(init, thread, '{"goal":null}', "/synthetic/codex", "/wrong", session, False) == 1
    assert recovery_plan(init, thread, '{"goal":null}', "/synthetic/codex", "/synthetic/work", "bad", False) == 1
    assert recovery_mutation_confirmed(3, '{"turn":{"id":"t"}}', session)
    assert not recovery_mutation_confirmed(3, '{"turn":{"id":""}}', session)
    assert not recovery_mutation_confirmed(2, '{"goal":{"status":"active","threadId":"other"}}', session)
    print("runtime recovery tests passed")
