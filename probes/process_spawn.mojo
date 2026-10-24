"""Synthetic child used by process-spawn checks."""

from std.sys import argv
from std.os import getenv
from std.os.process import Process
from std.collections import List
from modex.paths import absolute_path

from modex.process_spawn import spawn_with_env


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "child":
        if getenv("MODEX_CHILD_MARKER") != "synthetic":
            raise Error("child environment mismatch")
        print("child-ok")
        return

    var child_args = List[String]()
    child_args.append("child")
    var child_env = List[String]()
    child_env.append("MODEX_CHILD_MARKER=synthetic")
    var child = spawn_with_env(absolute_path(String(args[0])), child_args, child_env)
    var status = child.wait()
    if not status.exit_code or status.exit_code.value() != 0:
        raise Error("synthetic child failed")
    print("process spawn environment check: PASS")
