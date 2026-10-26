"""Test-only line protocol for deterministic recovery policy comparisons."""
from std.sys import argv
from modex.runtime_recovery import recovery_wire_action, recovery_plan


def main() raises:
    var args = argv()
    if len(args) == 7 and args[1] == "wire":
        print(recovery_wire_action(String(args[2]), String(args[3]), Int(args[4]), Int64(Int(args[5])), Int64(Int(args[6]))))
    elif len(args) == 9 and args[1] == "plan":
        print(recovery_plan(String(args[2]), String(args[3]), String(args[4]), String(args[5]), String(args[6]), String(args[7]), args[8] == "1"))
    else:
        raise Error("expected wire THREAD GOAL FLAGS BUDGET USED or plan INIT READ GOAL HOME WORK SESSION EXPECTED")
