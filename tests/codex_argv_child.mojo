"""Native synthetic Codex ELF for end-to-end argv[0] checks."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.os import getenv
from std.os.path import realpath
from std.sys import argv, exit

from modex.json import JsonDocument, quote_json


def _pid() raises -> String:
    var components = realpath("/proc/self").split("/")
    return String(components[len(components) - 1])


def _record(kind: String, arguments: List[String]) raises:
    var rendered_args = String("[")
    for index in range(1, len(arguments)):
        if index > 1:
            rendered_args += ","
        rendered_args += quote_json(arguments[index])
    rendered_args += "]"
    var line = (
        '{"kind":' + quote_json(kind)
        + ',"argv0":' + quote_json(arguments[0])
        + ',"pid":' + _pid()
        + ',"args":' + rendered_args + "}\n"
    )
    with open(getenv("MODEX_NATIVE_CODEX_LOG"), "a") as log:
        log.write(line)


def _preflight() raises:
    var input = RawFileDescriptor(0)
    var output = RawFileDescriptor(1)
    var buffer = List[UInt8](length=4096, fill=0)
    var pending = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            return
        for index in range(size):
            if buffer[index] != 10:
                pending.append(buffer[index])
                continue
            var request = JsonDocument(String(from_utf8=Span(pending)))
            var id_node = request.get(request.root, "id")
            if id_node < 0:
                pending.clear()
                continue
            var request_id = request.nodes[id_node].text
            var result = String("{}") if request_id == "1" else String('{"data":[]}')
            output.write_bytes(
                ('{"id":' + request_id + ',"jsonrpc":"2.0","result":' + result + "}\n").as_bytes()
            )
            pending.clear()


def main() raises:
    var arguments = argv()
    if len(arguments) < 2:
        raise Error("native Codex fixture requires an invocation")

    var version_probe = len(arguments) == 2 and arguments[1] == "--version"
    var help_probe = len(arguments) == 3 and arguments[1] == "app-server" and arguments[2] == "--help"
    var app_server = False
    var stdio = False
    for argument in arguments:
        if argument == "app-server":
            app_server = True
        if argument == "--stdio":
            stdio = True

    var kind = String("launch")
    if version_probe or help_probe:
        kind = "probe"
    elif app_server and stdio:
        kind = "preflight"
    var command_arguments = List[String]()
    for argument in arguments:
        command_arguments.append(String(argument))
    _record(kind, command_arguments)

    if version_probe:
        print(getenv("MODEX_TEST_CODEX_VERSION", "codex-cli 0.153.2"))
        return
    if help_probe:
        print("Codex app-server")
        return
    if app_server and stdio:
        _preflight()
        return
    exit(7)
