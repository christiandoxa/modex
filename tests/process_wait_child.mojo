"""Synthetic direct child for bounded process wait checks."""

from std.sys import argv
from std.sys._libc import exit
from std.time import sleep


def main() raises:
    var args = argv()
    if len(args) != 2:
        raise Error("child mode required")
    if args[1] == "exit-seven":
        exit(7)
    elif args[1] == "delayed-exit":
        sleep(0.02)
    elif args[1] == "hold-open":
        sleep(30.0)
    elif args[1] != "exit-zero":
        raise Error("invalid child mode")
