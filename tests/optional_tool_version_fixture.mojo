"""Native synthetic RTK executable for isolated Super dry-run checks."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.os import getenv
from std.os.path import exists
from std.sys import argv, exit, stderr
from std.time import sleep


def main() raises:
    var arguments = argv()
    var npx_probe = len(arguments) == 4 and arguments[1] == "--no-install" and arguments[2] == "@playwright/mcp" and arguments[3] == "--version"
    if (len(arguments) == 2 and arguments[1] == "--version") or npx_probe:
        var marker = getenv("SYNTHETIC_PROBE_MARKER", "\0")
        if marker != "\0":
            with open(marker, "w") as file:
                file.write("probe received unapproved environment")
        var home = getenv("HOME", "")
        var config = home + "/.rtk-version-fixture"
        var executable = String(arguments[0])
        if npx_probe:
            config = home + "/.npx-version-fixture"
            if exists(home + "/.npx-probe-marker-enabled"):
                with open(home + "/.npx-probe-invoked", "w") as file:
                    file.write("synthetic npx probe")
        if executable.find("/outside/codebase-memory-mcp") >= 0:
            with open(home + "/.codebase-probe-invoked", "w") as file:
                file.write("managed symlink target was executed")
        if executable.endswith("/codebase-memory-mcp"):
            config = home + "/.codebase-version-fixture"
            var version_override = executable + ".fixture"
            if exists(version_override):
                config = version_override^
        if executable.find("/.local/share/prodex-optimizers/rtk") >= 0:
            config = home + "/.rtk-managed-version-fixture"
        var version = String("rtk 1.1.0")
        if exists(config):
            var bytes: List[UInt8]
            with open(config, "r") as file:
                bytes = file.read_bytes(4096)
            version = String(from_utf8=Span(bytes))
        if version == "timeout":
            sleep(6.0)
        elif version == "invalid-stdout" or version == "invalid-stderr":
            var bad: List[UInt8] = [UInt8(255)]
            if version == "invalid-stderr":
                print("0.0.83")
                var output = RawFileDescriptor(2)
                output.write_bytes(Span(bad))
            else:
                var output = RawFileDescriptor(1)
                output.write_bytes(Span(bad))
                print("0.0.83", file=stderr)
            return
        elif version == "exit:7":
            print("synthetic failed version probe")
            exit(7)
        elif version.startswith("stderr:"):
            print(String(version[byte=7:]), file=stderr)
            return
        elif version == "empty":
            return
        print(version)
        return
    exit(1)
