"""Native checks for all transcript events projected from one record."""

from std.collections import List
from std.testing import assert_equal

from modex.log_transcript import transcript_events

comptime TIMESTAMP = "2026-10-24T01:02:03Z"


def check(line: String, expected: List[Tuple[String, String, String]]) raises:
    assert_equal(transcript_events(line), expected)


def main() raises:
    var expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "prompt-engineering", "Read carefully"))
    expected.append((TIMESTAMP, "session-context", "provider=synthetic-provider originator=synthetic-cli"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"session_meta\",\"payload\":{\"base_instructions\":{\"text\":\"Read carefully\"},\"model_provider\":\"synthetic-provider\",\"originator\":\"synthetic-cli\"}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "session-context", "provider=synthetic-provider"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"session_meta\",\"payload\":{\"base_instructions\":{\"text\":\" \\u2003\\n\"},\"provider\":\"synthetic-provider\"}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "prompt-engineering", "prompt only"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"session_meta\",\"payload\":{\"base_instructions\":{\"text\":\"prompt only\"}}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "turn-context", "model=synthetic-model effort=high"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"turn_context\",\"payload\":{\"model\":\"synthetic-model\",\"effort\":\"high\"}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "tool-call:shell", "echo safe"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"response_item\",\"payload\":{\"type\":\"shell_call\",\"command\":\"echo safe\"}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    expected.append((TIMESTAMP, "", "empty role marker"))
    check(
        "{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"response_item\",\"payload\":{\"type\":\"message\",\"role\":\"\",\"content\":[{\"text\":\"empty role marker\"}]}}",
        expected,
    )

    expected = List[Tuple[String, String, String]]()
    check("not JSON", expected)
    check("{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"session_meta\",\"payload\":[]}", expected)
    check("{\"timestamp\":\"2026-10-24T01:02:03Z\",\"type\":\"session_meta\",\"payload\":{}}", expected)
    print("Transcript all-events projection checks: PASS")
