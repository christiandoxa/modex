"""Exercise the production app-server RPC transport with a synthetic peer."""

from std.collections import List
from std.sys import argv, exit, stderr

from modex.app_server_rpc import run_super_hook_trust_preflight


def main():
    var arguments = argv()
    if len(arguments) < 3:
        print("Error: expected CODEX_BINARY WORKSPACE [KEY=VALUE ...]", file=stderr)
        exit(2)
        return
    var environment = List[String]()
    for index in range(3, len(arguments)):
        environment.append(String(arguments[index]))
    try:
        var legacy = run_super_hook_trust_preflight(
            String(arguments[1]),
            String(arguments[2]),
            [String("--model"), "fixture-model"],
            environment,
        )
        print("LegacyBypass" if legacy else "Trusted")
    except error:
        print("Error: " + String(error), file=stderr)
        exit(1)
