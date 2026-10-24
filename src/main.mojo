from std.sys import argv, exit, stderr


def main():
    var args = argv()
    if len(args) == 2 and (args[1] == "--version" or args[1] == "-V"):
        print("modex 0.1.0-dev")
        return
    print(
        "Error: this Modex development build has not implemented the requested command",
        file=stderr,
    )
    exit(1)
