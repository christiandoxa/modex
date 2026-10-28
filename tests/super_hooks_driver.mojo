"""Test-only inherited-pipe transport for the native hook-trust protocol."""

from std.collections import List, Span
from std.io import FileHandle, RawFileDescriptor
from std.net._sys.unix import F_GETFL, F_SETFL, O_NONBLOCK
from std.sys import argv, exit
from std.sys._libc import fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.time import perf_counter, sleep

from modex.super_hooks import HOOK_TRUST_MAX_RPC_LINE_BYTES, HOOK_TRUST_RPC_TIMEOUT_MS, HookTrustSession


def write_all(fd: Int32, text: String) raises:
    var deadline = perf_counter() + Float64(HOOK_TRUST_RPC_TIMEOUT_MS) / 1000.0
    var bytes = text.as_bytes()
    var offset = 0
    var output = FileHandle()
    # Borrow the inherited descriptor and detach it before FileHandle destruction.
    output.handle = Int(fd)
    try:
        while offset < len(bytes):
            if perf_counter() >= deadline:
                raise Error("hook-trust driver request write timed out")
            var written: Int
            try:
                written = output.write_once(bytes[offset:min(len(bytes), offset + 8192)])
            except:
                var error = get_errno()
                if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                    raise Error("hook-trust driver request write failed")
                sleep(0.001)
                continue
            if written == 0:
                raise Error("hook-trust driver request write failed")
            offset += written
    except:
        output.handle = -1
        raise
    output.handle = -1


def read_session(workspace: String) raises -> Bool:
    var session = HookTrustSession(workspace)
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var pending = List[UInt8]()
    var size = 0
    var offset = 0
    var eof = False
    while not session.done:
        # Keep this replay aligned with the historical 0.439.2 oracle fixture.
        var request = session.request().replace('"version":"0.165.1"', '"version":"0.439.2"')
        write_all(1, request + "\n")
        var deadline = perf_counter() + Float64(HOOK_TRUST_RPC_TIMEOUT_MS) / 1000.0
        var accepted = False
        while not accepted:
            if perf_counter() >= deadline:
                if offset < size:
                    raise Error(session.timeout_message())
                raise Error("Codex hook-trust preflight " + session.method() + " failed: timed out waiting on channel")
            if offset < size:
                var byte = buffer[offset]
                offset += 1
                if byte != 10:
                    if len(pending) >= HOOK_TRUST_MAX_RPC_LINE_BYTES:
                        raise Error("hook-trust driver stdout line exceeds its supported size")
                    pending.append(byte)
                    continue
            elif eof:
                if not pending:
                    raise Error("Codex hook-trust preflight " + session.method() + " failed: channel is empty and sending half is closed")
            else:
                try:
                    size = input.read_bytes(Span(buffer))
                except:
                    var error = get_errno()
                    if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                        raise Error("Codex hook-trust preflight stdout failed: could not read stdout")
                    sleep(0.001)
                    continue
                offset = 0
                eof = size == 0
                continue
            var line: String
            try:
                line = String(from_utf8=Span(pending))
            except:
                raise Error("Codex hook-trust preflight stdout failed: stream did not contain valid UTF-8")
            pending.clear()
            accepted = session.accept(line)
    return session.legacy


def run(workspace: String) raises -> Bool:
    var input_flags = fcntl(0, F_GETFL)
    var output_flags = fcntl(1, F_GETFL)
    if input_flags < 0 or output_flags < 0:
        raise Error("hook-trust driver could not inspect inherited pipes")
    if fcntl(0, F_SETFL, input_flags | O_NONBLOCK) < 0:
        raise Error("hook-trust driver could not set nonblocking input")
    if fcntl(1, F_SETFL, output_flags | O_NONBLOCK) < 0:
        _ = fcntl(0, F_SETFL, input_flags)
        raise Error("hook-trust driver could not set nonblocking output")
    try:
        var legacy = read_session(workspace)
        _ = fcntl(0, F_SETFL, input_flags)
        _ = fcntl(1, F_SETFL, output_flags)
        return legacy
    except:
        _ = fcntl(0, F_SETFL, input_flags)
        _ = fcntl(1, F_SETFL, output_flags)
        raise


def main():
    var arguments = argv()
    if len(arguments) != 2:
        try:
            write_all(2, "Error: expected WORKSPACE\n")
        except:
            pass
        exit(1)
        return
    try:
        var legacy = run(String(arguments[1]))
        write_all(2, "LegacyBypass\n" if legacy else "Trusted\n")
    except error:
        try:
            write_all(2, "Error: " + String(error) + "\n")
        except:
            pass
        exit(1)
