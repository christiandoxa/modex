# Prodex 0.439.2 gate/setup diff: 81c1a01933bc33f536a24452c3fd72c3f8d0b1f3 -> 72b77478a5198fc5da6b4d2253137f9cdbf43be9.
from modex.runtime_recovery import (
    quota_recovery_alternate_eligible,
    quota_recovery_decision,
    QUOTA_HANDOFF_RETRY_FULL_HISTORY,
    QUOTA_HANDOFF_PROCEED,
)
from std.sys import argv


def main() raises:
    var report = len(argv()) > 1
    for context_allowed in [False, True]:
        for auth_compatible in [False, True]:
            for supports_runtime in [False, True]:
                for auth_failure_active in [False, True]:
                    for quota_quarantined in [False, True]:
                        for five_hour in range(5):
                            for weekly in range(5):
                                var eligible = quota_recovery_alternate_eligible(
                                    context_allowed, auth_compatible, supports_runtime,
                                    auth_failure_active, quota_quarantined, five_hour, weekly,
                                )
                                if report:
                                    print(
                                        "A", Int(context_allowed), Int(auth_compatible),
                                        Int(supports_runtime), Int(auth_failure_active),
                                        Int(quota_quarantined), five_hour, weekly, Int(eligible),
                                    )

    for hard_affinity in [False, True]:
        for owner_matches in [False, True]:
            for full_history in [False, True]:
                for retry_available in [False, True]:
                    for alternate_recoverable in [False, True]:
                        for five_hour in range(5):
                            for weekly in range(5):
                                var decision = quota_recovery_decision(
                                    hard_affinity, owner_matches, full_history,
                                    retry_available, alternate_recoverable, five_hour, weekly,
                                )
                                if report:
                                    print(
                                        "D", Int(hard_affinity), Int(owner_matches),
                                        Int(full_history), Int(retry_available),
                                        Int(alternate_recoverable), five_hour, weekly, decision,
                                    )

    var invalid_status_rejected = False
    try:
        _ = quota_recovery_decision(True, True, True, True, True, 5, 0)
    except:
        invalid_status_rejected = True
    assert invalid_status_rejected
    assert quota_recovery_alternate_eligible(True, True, True, False, False, 0, 1)
    assert quota_recovery_alternate_eligible(True, True, True, False, False, 0, 0)
    assert not quota_recovery_alternate_eligible(True, True, True, False, False, 3, 1)
    assert not quota_recovery_alternate_eligible(True, True, True, False, False, 1, 3)
    var unknown_quota_alternate = quota_recovery_alternate_eligible(
        True, True, True, False, False, 0, 0,
    )
    assert quota_recovery_decision(
        True, True, True, True, unknown_quota_alternate, 3, 0,
    ) == QUOTA_HANDOFF_RETRY_FULL_HISTORY
    assert quota_recovery_decision(True, True, True, True, True, 3, 1) == QUOTA_HANDOFF_RETRY_FULL_HISTORY
    assert quota_recovery_decision(True, True, True, True, True, 1, 3) == QUOTA_HANDOFF_RETRY_FULL_HISTORY
    assert quota_recovery_decision(True, True, True, True, True, 0, 1) == QUOTA_HANDOFF_PROCEED
    assert quota_recovery_decision(True, True, True, True, True, 1, 1) == QUOTA_HANDOFF_PROCEED
    assert quota_recovery_decision(True, True, True, False, True, 3, 1) == QUOTA_HANDOFF_PROCEED
    if report:
        print("INVALID", Int(invalid_status_rejected))
    else:
        print("Unconnected quota handoff policy checks: PASS")
