"""Synthetic child that checks argv and its private environment."""

from std.sys import argv
from std.os import getenv
from std.sys._libc import exit


def main() raises:
    var args = argv()
    if len(args) == 2 and args[1] == "check-argv0":
        if args[0] != "requested-codex" or getenv("MODEX_EXPECT_ARGV0") != args[0]:
            raise Error("child argv0 mismatch")
        return
    if len(args) == 2 and args[1] == "exit-nonzero":
        exit(7)
    if len(args) != 6:
        raise Error("child argv length mismatch")
    if args[1] != "arg-one" or args[2] != "arg two" or args[3] != "":
        raise Error("child argv content mismatch")
    if args[4] != "雪とé" or args[5] != "long-" + String("x" * 8192):
        raise Error("child argv long/unicode mismatch")
    if getenv("MODEX_CHILD_MARKER") != "synthetic":
        raise Error("child environment mismatch")
    if getenv("MODEX_PARENT_SENTINEL", "absent") != "absent":
        raise Error("child inherited parent environment")
    if getenv("MODEX_LONG_VALUE") != String("v" * 8192):
        raise Error("child long environment mismatch")
    print("synthetic-child-ok")
