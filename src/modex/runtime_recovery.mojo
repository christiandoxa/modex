"""Pinned native recovery policy; callers own transport and monotonic observations."""
from .json import JsonDocument, JSON_NULL, JSON_BOOL, JSON_NUMBER
from std.collections import List
from std.os.path import realpath

comptime RECOVERY_DEFER = 0
comptime RECOVERY_STOP = 1
comptime RECOVERY_RESUME_GOAL = 2
comptime RECOVERY_CONTINUE_TURN = 3
comptime QUOTA_WINDOW_EXHAUSTED = 3
comptime QUOTA_HANDOFF_PROCEED = 0
comptime QUOTA_HANDOFF_RETRY_FULL_HISTORY = 1

# shortcut: no production recovery caller, connect after account/affinity ownership exists.


def _quota_windows_valid(five_hour_status: Int, weekly_status: Int) -> Bool:
    return 0 <= five_hour_status <= 4 and 0 <= weekly_status <= 4


def _quota_window_exhausted(status: Int) -> Bool:
    # Match the pinned Mojo WINDOW_GUARD: exhausted is status 3.
    return status == QUOTA_WINDOW_EXHAUSTED


def quota_recovery_alternate_eligible(
    context_allowed: Bool,
    auth_compatible: Bool,
    supports_runtime: Bool,
    auth_failure_active: Bool,
    quota_quarantined: Bool,
    five_hour_status: Int,
    weekly_status: Int,
) raises -> Bool:
    """A recoverable alternate may still wait on capacity or cooldown."""
    if not _quota_windows_valid(five_hour_status, weekly_status):
        raise Error("invalid quota window status")
    return (
        context_allowed and auth_compatible and supports_runtime
        and not auth_failure_active and not quota_quarantined
        and not _quota_window_exhausted(five_hour_status)
        and not _quota_window_exhausted(weekly_status)
    )


def quota_recovery_decision(
    hard_affinity: Bool,
    owner_matches: Bool,
    full_history_reconstructable: Bool,
    retry_available: Bool,
    alternate_recoverable: Bool,
    owner_five_hour_status: Int,
    owner_weekly_status: Int,
) raises -> Int:
    """Unconnected signal policy; PROCEED grants neither admission nor replay."""
    if not _quota_windows_valid(owner_five_hour_status, owner_weekly_status):
        raise Error("invalid quota window status")
    if (
        hard_affinity and owner_matches and full_history_reconstructable
        and retry_available and alternate_recoverable
        and (
            _quota_window_exhausted(owner_five_hour_status)
            or _quota_window_exhausted(owner_weekly_status)
        )
    ):
        return QUOTA_HANDOFF_RETRY_FULL_HISTORY
    return QUOTA_HANDOFF_PROCEED


def recovery_retry_delay_ms(attempts: UInt32) -> UInt64:
    if attempts == 0:
        return 0
    if attempts >= 5:
        return 60000
    return UInt64(5000) << UInt64(attempts - 1)


def _deadline(now: UInt64, delay: UInt64) -> UInt64:
    return UInt64.MAX if now > UInt64.MAX - delay else now + delay


struct NativeRecoveryRetry:
    var session: String
    var has_session: Bool
    var progress: UInt64
    var failure: UInt64
    var has_failure: Bool
    var attempts: UInt32
    var next_attempt_at: UInt64

    def __init__(out self, now_ms: UInt64):
        self.session = ""
        self.has_session = False
        self.progress = 0
        self.failure = 0
        self.has_failure = False
        self.attempts = 0
        self.next_attempt_at = now_ms

    def ready(mut self, session: String, progress: UInt64, failure: UInt64, now_ms: UInt64) -> Bool:
        if not self.has_session or self.session != session or self.progress != progress:
            self.session = session
            self.has_session = True
            self.progress = progress
            self.has_failure = False
            self.attempts = 0
            self.next_attempt_at = now_ms
        if not self.has_failure or self.failure != failure:
            self.failure = failure
            self.has_failure = True
            self.next_attempt_at = _deadline(now_ms, recovery_retry_delay_ms(self.attempts))
        return now_ms >= self.next_attempt_at

    def completed_attempt(mut self, now_ms: UInt64):
        if self.attempts < UInt32.MAX:
            self.attempts += 1
        self.next_attempt_at = _deadline(now_ms, recovery_retry_delay_ms(self.attempts))


# Flags: goal=1, budget present=2/null=4/i64=8, used i64=16, expected goal=32.
def recovery_wire_action(thread_status: String, goal_status: String, flags: Int, budget: Int64, used: Int64) raises -> Int:
    if flags < 0 or flags > 63:
        raise Error("invalid recovery wire flags")
    if thread_status != "idle" and thread_status != "systemError":
        return RECOVERY_DEFER
    if flags & 1 == 0:
        return RECOVERY_STOP if flags & 32 else RECOVERY_CONTINUE_TURN
    if goal_status != "active" and goal_status != "blocked" and goal_status != "usageLimited":
        return RECOVERY_STOP
    if flags & 2 and not flags & 4:
        if not flags & 8 or not flags & 16 or budget <= 0 or used < 0 or used >= budget:
            return RECOVERY_STOP
    return RECOVERY_RESUME_GOAL


def _uuid(session: String) -> Bool:
    var value = session
    if value.startswith("urn:uuid:"):
        value = String(session[byte=9:])
    elif value.startswith("{") and value.endswith("}"):
        value = String(session[byte=1:session.byte_length() - 1])
    if value.byte_length() != 32 and value.byte_length() != 36:
        return False
    for i in range(value.byte_length()):
        var c = Int(value.as_bytes()[i])
        if value.byte_length() == 36 and (i == 8 or i == 13 or i == 18 or i == 23):
            if c != 45:
                return False
        elif not (48 <= c <= 57 or 65 <= c <= 70 or 97 <= c <= 102):
            return False
    return True


def _normalized_path(path: String) -> String:
    try:
        return realpath(path)
    except:
        pass
    var parts = List[String]()
    var rooted = path.startswith("/")
    for part in path.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if len(parts) and parts[len(parts) - 1] != "..":
                _ = parts.pop()
            elif not rooted:
                parts.append("..")
        else:
            parts.append(String(part))
    var lexical = String("/" if rooted else "")
    for part in parts:
        if lexical and lexical != "/":
            lexical += "/"
        lexical += part
    if not lexical:
        lexical = "."
    var cursor = lexical
    var suffix = String()
    while cursor != "/" and cursor != ".":
        var slash = cursor.rfind("/")
        var name = String(cursor[byte=slash + 1:])
        var parent = String(cursor[byte=:slash]) if slash > 0 else String("/" if slash == 0 else ".")
        suffix = "/" + name + suffix
        try:
            var resolved = realpath(parent)
            return (String(resolved[byte=:resolved.byte_length() - 1]) if resolved.endswith("/") else resolved) + suffix
        except:
            pass
        cursor = parent
    return lexical


def _same_path(actual: String, expected: String) -> Bool:
    return Bool(actual) and Bool(expected) and "\x00" not in actual and "\x00" not in expected and _normalized_path(actual) == _normalized_path(expected)


def _integer(doc: JsonDocument, node: Int) -> Tuple[Bool, Int64]:
    if node < 0 or doc.nodes[node].kind != JSON_NUMBER:
        return False, 0
    var text = doc.nodes[node].text
    if text == "-0":
        return False, 0
    var negative = text.startswith("-")
    var magnitude = UInt64(0)
    var maximum = UInt64(1) << 63 if negative else UInt64(Int64.MAX)
    for i in range(1 if negative else 0, text.byte_length()):
        var byte = Int(text.as_bytes()[i])
        if byte < 48 or byte > 57:
            return False, 0
        var digit = UInt64(byte - 48)
        if magnitude > (maximum - digit) // 10:
            return False, 0
        magnitude = magnitude * 10 + digit
    if negative:
        return True, Int64.MIN if magnitude == UInt64(1) << 63 else -Int64(magnitude)
    return True, Int64(magnitude)


def recovery_plan(initialized_json: String, thread_read_json: String, goal_get_json: String, codex_home: String, workspace: String, session: String, expected_goal: Bool) raises -> Int:
    if not _uuid(session):
        return RECOVERY_STOP
    var initialized = JsonDocument(initialized_json)
    if not _same_path(initialized.string(initialized.get(initialized.root, "codexHome")), codex_home):
        return RECOVERY_STOP
    var read = JsonDocument(thread_read_json)
    var thread = read.get(read.root, "thread")
    if thread < 0:
        return RECOVERY_DEFER
    var ephemeral = read.get(thread, "ephemeral")
    var direct = read.get(thread, "canAcceptDirectInput")
    if (read.string(read.get(thread, "id")) != session or read.string(read.get(thread, "sessionId")) != session
        or ephemeral < 0 or read.nodes[ephemeral].kind != JSON_BOOL or read.nodes[ephemeral].text != "false"
        or direct < 0 or read.nodes[direct].kind != JSON_BOOL or read.nodes[direct].text != "true"
        or not _same_path(read.string(read.get(thread, "cwd")), workspace)):
        return RECOVERY_STOP
    var goals = JsonDocument(goal_get_json)
    var goal = goals.get(goals.root, "goal")
    if goal < 0:
        return RECOVERY_DEFER
    var flags = 32 if expected_goal else 0
    var budget = Int64(0)
    var used = Int64(0)
    if goals.nodes[goal].kind != JSON_NULL:
        if goals.string(goals.get(goal, "threadId")) != session:
            return RECOVERY_STOP
        flags |= 1
        var limit = goals.get(goal, "tokenBudget")
        if limit >= 0:
            flags |= 2
            if goals.nodes[limit].kind == JSON_NULL:
                flags |= 4
        var parsed = _integer(goals, limit)
        if parsed[0]:
            flags |= 8
            budget = parsed[1]
        parsed = _integer(goals, goals.get(goal, "tokensUsed"))
        if parsed[0]:
            flags |= 16
            used = parsed[1]
    var status = read.get(thread, "status")
    return recovery_wire_action(read.string(read.get(status, "type")), goals.string(goals.get(goal, "status")), flags, budget, used)


def recovery_mutation_confirmed(action: Int, result_json: String, session: String) raises -> Bool:
    var result = JsonDocument(result_json)
    if action == RECOVERY_RESUME_GOAL:
        var goal = result.get(result.root, "goal")
        return result.string(result.get(goal, "threadId")) == session and result.string(result.get(goal, "status")) == "active"
    if action == RECOVERY_CONTINUE_TURN:
        var turn = result.get(result.root, "turn")
        return Bool(result.string(result.get(turn, "id")))
    return False
