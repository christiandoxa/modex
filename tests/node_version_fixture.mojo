"""Native synthetic Node executable for optional-tool dry-run controls."""

from std.sys import argv, exit


def main() raises:
    var arguments = argv()
    if len(arguments) == 2 and arguments[1] == "--version":
        print("v20.18.1")
        return
    exit(1)
