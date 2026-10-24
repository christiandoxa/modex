from std.collections import List
from std.sys import argv, exit, stderr

from modex.cli import parse_session_options
from modex.sessions import inspect_sessions


def main():
    var args = List[String]()
    for arg in argv():
        args.append(String(arg))
    if len(args) == 2 and (args[1] == "--version" or args[1] == "-V"):
        print("modex 0.1.0-dev")
        return
    if len(args) >= 2 and args[1] == "session":
        try:
            var options = parse_session_options(args)
            try:
                var output = inspect_sessions(options)
                print(output, end="")
            except error:
                print("Error:", error, file=stderr)
                exit(1)
        except error:
            print("error:", error, file=stderr)
            exit(2)
        return
    print(
        "Error: this Modex development build has not implemented the requested command",
        file=stderr,
    )
    exit(1)
