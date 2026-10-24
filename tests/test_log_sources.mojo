from std.testing import assert_true
from modex.log_upstream_follow import runtime_log_recording_enabled_value

def main() raises:
    for value in ["1", "true", "TRUE", " yes\t", "\ton\r\n", "\u00a0TrUe\u00a0"]:
        assert_true(runtime_log_recording_enabled_value(value))
    for value in ["", "0", "false", "off", "t r u e"]:
        assert_true(not runtime_log_recording_enabled_value(value))
    print("recording-enabled predicate: PASS")
