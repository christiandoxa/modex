"""Frozen noisy-command classification for provider tool argument rewriting."""

from std.collections import List, Span

from .text import is_whitespace


def prefixed_noisy_command(command: String) raises -> Optional[String]:
    if command.byte_length() > 64 * 1024 * 1024:
        raise Error("RTK command exceeds the supported size")
    var start = 0
    var index = 0
    var quote = UInt8(0)
    var escaped = False
    while index < command.byte_length():
        var byte = command.as_bytes()[index]
        if escaped:
            escaped = False
        elif quote == 39:
            if byte == 39: quote = 0
        elif quote == 34:
            if byte == 34: quote = 0
            elif byte == 92: escaped = True
        elif byte == 34 or byte == 39:
            quote = byte
        elif byte == 92:
            escaped = True
        else:
            var separator = 0
            if index + 1 < command.byte_length() and ((byte == 38 and command.as_bytes()[index + 1] == 38) or (byte == 124 and command.as_bytes()[index + 1] == 124)):
                separator = 2
            elif byte == 59 or byte == 124 or byte == 10:
                separator = 1
            if separator:
                if noisy_segment(command, start, index):
                    return Optional[String]("rtk " + command)
                index += separator
                start = index
                continue
        index += 1
    if noisy_segment(command, start, index):
        return Optional[String]("rtk " + command)
    return Optional[String]()


def noisy_segment(command: String, start: Int, end: Int) -> Bool:
    var cursor = skip_space(command, start, end)
    while cursor < end:
        var token_end = cursor
        while token_end < end and not space_width(command, token_end):
            token_end += utf8_width(command.as_bytes()[token_end])
        var raw = command[byte=cursor:token_end]
        var token = decoded_token(raw)
        if token and token.value() == "rtk":
            return False
        var assignment = is_assignment(token.value()) if token else is_assignment(raw)
        if assignment:
            cursor = skip_space(command, token_end, end)
            continue
        if not token:
            return False
        var executable = token.value()
        var slash = -1
        for index in range(executable.byte_length()):
            if executable.as_bytes()[index] == 47:
                slash = index
        var basename = String(executable[byte=slash + 1:])
        if basename == "pytest" or basename == "rg" or basename == "find" or basename == "ls" or basename == "tree" or basename == "echo":
            return True
        cursor = skip_space(command, token_end, end)
        while cursor < end:
            token_end = cursor
            while token_end < end and not space_width(command, token_end):
                token_end += utf8_width(command.as_bytes()[token_end])
            token = decoded_token(command[byte=cursor:token_end])
            if token and noisy_subcommand(basename, token.value()):
                return True
            cursor = skip_space(command, token_end, end)
        return False
    return False


def decoded_token(raw: StringSlice) -> Optional[String]:
    if raw.byte_length() <= 4096 and raw.find("'") < 0 and raw.find('"') < 0 and raw.find("\\") < 0:
        return Optional[String](String(raw))
    var bytes = List[UInt8]()
    var quote = UInt8(0)
    var escaped = False
    for byte in raw.as_bytes():
        if escaped:
            bytes.append(byte)
            escaped = False
        elif quote == 39:
            if byte == 39: quote = 0
            else: bytes.append(byte)
        elif quote == 34:
            if byte == 34: quote = 0
            elif byte == 92: escaped = True
            else: bytes.append(byte)
        elif byte == 34 or byte == 39:
            quote = byte
        elif byte == 92:
            escaped = True
        else:
            bytes.append(byte)
        # The frozen classifier caps decoded tokens, not environment values.
        if len(bytes) > 4096:
            return Optional[String]()
    try:
        return Optional[String](String(from_utf8=Span(bytes)))
    except:
        return Optional[String]()


def is_assignment(token: StringSlice) -> Bool:
    var equals = token.find("=")
    if equals < 1 or equals + 1 >= token.byte_length():
        return False
    for index in range(equals):
        var byte = Int(token.as_bytes()[index])
        if byte != 95 and not (65 <= byte <= 90 or 97 <= byte <= 122 or (index > 0 and 48 <= byte <= 57)):
            return False
    return True


def noisy_subcommand(command: String, subcommand: String) -> Bool:
    if command == "git":
        return subcommand == "diff" or subcommand == "show" or subcommand == "log" or subcommand == "status" or subcommand == "grep" or subcommand == "blame"
    if command == "cargo":
        return subcommand == "test" or subcommand == "build" or subcommand == "check" or subcommand == "clippy" or subcommand == "bench" or subcommand == "run"
    if command == "npm":
        return subcommand == "test" or subcommand == "run" or subcommand == "build" or subcommand == "install" or subcommand == "ci" or subcommand == "update" or subcommand == "audit"
    if command == "yarn":
        return subcommand == "test" or subcommand == "run" or subcommand == "build" or subcommand == "install" or subcommand == "add" or subcommand == "upgrade"
    if command == "pnpm":
        return subcommand == "test" or subcommand == "run" or subcommand == "build" or subcommand == "install" or subcommand == "add" or subcommand == "update"
    if command == "bun":
        return subcommand == "test" or subcommand == "run" or subcommand == "build" or subcommand == "install" or subcommand == "add"
    if command == "go":
        return subcommand == "test" or subcommand == "build" or subcommand == "vet"
    if command == "docker":
        return subcommand == "build" or subcommand == "compose" or subcommand == "logs" or subcommand == "pull" or subcommand == "push" or subcommand == "run"
    if command == "kubectl":
        return subcommand == "logs" or subcommand == "describe" or subcommand == "get" or subcommand == "events" or subcommand == "top"
    return command == "claw-compactor" and subcommand == "benchmark"


def skip_space(source: String, start: Int, end: Int) -> Int:
    var index = start
    while index < end:
        var width = space_width(source, index)
        if not width:
            break
        index += width
    return index


def space_width(source: String, index: Int) -> Int:
    var byte = source.as_bytes()[index]
    if byte < 128:
        return 1 if is_whitespace(Int(byte)) else 0
    for scalar in source[byte=index:].codepoints():
        return utf8_width(byte) if is_whitespace(Int(scalar)) else 0
    return 0


def utf8_width(byte: UInt8) -> Int:
    return 1 if byte < 128 else 2 if byte < 224 else 3 if byte < 240 else 4
