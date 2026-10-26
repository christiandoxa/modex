from std.collections import List
from std.testing import assert_equal, assert_true

from modex.cli import parse_session_options


def rejects(args: List[String], expected: String) raises:
    var failed = False
    try:
        _ = parse_session_options(args)
    except error:
        failed = True
        assert_equal(String(error), expected)
    assert_true(failed)


def main() raises:
    rejects(
        [String("modex"), "session", "--", "--help"],
        "error: unrecognized subcommand '--help'\n\n  tip: a similar subcommand exists: 'help'\n\nUsage: modex session <COMMAND>\n\nFor more information, try '--help'.\n",
    )
    rejects(
        [String("modex"), "session", "--", "--json"],
        "error: unrecognized subcommand '--json'\n\nUsage: modex session <COMMAND>\n\nFor more information, try '--help'.\n",
    )
    rejects(
        [String("modex"), "session", "--", "-h"],
        "error: unrecognized subcommand '-h'\n\nUsage: modex session <COMMAND>\n\nFor more information, try '--help'.\n",
    )
    rejects(
        [String("modex"), "session", "--", "lits"],
        "error: unrecognized subcommand 'lits'\n\n  tip: a similar subcommand exists: 'list'\n\nUsage: modex session <COMMAND>\n\nFor more information, try '--help'.\n",
    )
    rejects(
        [String("modex"), "session", "--", "list"],
        "error: unexpected argument 'list' found\n\n  tip: subcommand 'list' exists; to use it, remove the '--' before it\n\nUsage: modex session <COMMAND>\n\nFor more information, try '--help'.\n",
    )
    print("Session root subcommand errors: PASS")
