"""Run the bounded Codex app-server hook-trust preflight over stdio pipes."""

from std.collections import List, Span
from std.io import FileHandle, RawFileDescriptor
from std.net._sys.unix import F_GETFL, F_SETFL, O_NONBLOCK
from std.os.process import Pipe, Process
from std.pathlib import cwd
from std.sys._libc import fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.time import perf_counter, sleep

from .app_server_args import project_app_server_config_args
from .process_spawn import spawn_with_env_stdio
from .super_hooks import HOOK_TRUST_MAX_RPC_LINE_BYTES, HOOK_TRUST_RPC_TIMEOUT_MS, HookTrustSession

comptime IO_CHUNK_BYTES = 8192


struct _RpcReader:
    var bytes: List[UInt8]
    var offset: Int
    var count: Int
    var line: List[UInt8]
    var eof: Bool

    def __init__(out self):
        self.bytes = List[UInt8](length=IO_CHUNK_BYTES, fill=0)
        self.offset = 0
        self.count = 0
        self.line = List[UInt8]()
        self.eof = False

    def next_line(mut self, fd: Int32, deadline: Float64, method: String) raises -> String:
        while True:
            while self.offset < self.count:
                var byte = self.bytes[self.offset]
                self.offset += 1
                if byte == 10:
                    var result = self._string_line(method)
                    return result
                if len(self.line) >= HOOK_TRUST_MAX_RPC_LINE_BYTES:
                    raise Error("Codex hook-trust preflight stdout line exceeds its supported size")
                self.line.append(byte)

            if self.eof:
                if self.line:
                    return self._string_line(method)
                raise Error("Codex hook-trust preflight " + method + " failed: receiving on a closed channel")
            if perf_counter() >= deadline:
                raise Error("Codex hook-trust preflight " + method + " failed: timed out waiting on channel")

            var input = RawFileDescriptor(fd)
            try:
                self.count = input.read_bytes(Span(self.bytes))
            except:
                var error = get_errno()
                if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                    raise Error("Codex hook-trust preflight stdout failed: could not read stdout")
                sleep(0.001)
                continue
            self.offset = 0
            self.eof = self.count == 0

    def _string_line(mut self, method: String) raises -> String:
        var result: String
        try:
            result = String(from_utf8=Span(self.line))
        except:
            raise Error("Codex hook-trust preflight " + method + " failed: stream did not contain valid UTF-8")
        self.line.clear()
        return result


def _set_nonblocking(fd: Int32) raises:
    var flags = fcntl(fd, F_GETFL, 0)
    if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
        raise Error("Codex hook-trust preflight could not configure a nonblocking pipe")


def _write_request(fd: Int32, request: String, deadline: Float64, method: String) raises:
    if request.byte_length() > HOOK_TRUST_MAX_RPC_LINE_BYTES:
        raise Error("Codex hook-trust preflight request exceeds its supported size")
    var bytes = request.as_bytes()
    var offset = 0
    var output = FileHandle()
    # Borrow the pipe descriptor and detach it before FileHandle destruction.
    output.handle = Int(fd)
    try:
        while offset < len(bytes):
            if perf_counter() >= deadline:
                raise Error("Codex hook-trust preflight " + method + " failed: timed out waiting on channel")
            var written: Int
            try:
                written = output.write_once(bytes[offset:min(len(bytes), offset + IO_CHUNK_BYTES)])
            except:
                var error = get_errno()
                if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                    raise Error("Codex hook-trust preflight " + method + " failed: request write failed")
                sleep(0.001)
                continue
            if written == 0:
                raise Error("Codex hook-trust preflight " + method + " failed: request pipe is closed")
            offset += written
    except:
        output.handle = -1
        raise
    output.handle = -1


def _stop_child(mut child: Process) raises:
    var status = child.poll()
    if not status.has_exited():
        if not child.kill():
            status = child.poll()
            if not status.has_exited():
                raise Error("Codex hook-trust preflight failed to terminate app-server")
    _ = child.wait()


def _spawn_app_server(binary: String, args: List[String], environment: List[String], stdin_fd: Int32, stdout_fd: Int32) raises -> Process:
    try:
        with open("/dev/null", "w") as stderr:
            return spawn_with_env_stdio(binary, args, environment, stdin_fd, stdout_fd, RawFileDescriptor(stderr).value)
    except error:
        raise Error("failed to start Codex hook-trust preflight with " + binary + ": " + String(error))


def _run_session(mut session: HookTrustSession, input: Pipe, output: Pipe) raises:
    var reader = _RpcReader()
    var output_fd = output.fd_in.value().value
    while not session.done:
        var method = session.method()
        var deadline = perf_counter() + Float64(HOOK_TRUST_RPC_TIMEOUT_MS) / 1000.0
        _write_request(input.fd_out.value().value, session.request() + "\n", deadline, method)
        while True:
            var line = reader.next_line(output_fd, deadline, method)
            if session.accept(line):
                break


def run_super_hook_trust_preflight(binary: String, workspace: String, runtime_args: List[String], environment: List[String]) raises -> Bool:
    """Return true only when Codex lacks a hook-trust RPC and needs legacy bypass.

    `environment` is the complete child environment, including `CODEX_HOME`.
    The preflight inherits the current directory, which must be `workspace`.
    """
    if not workspace.startswith("/") or String(cwd()) != workspace:
        raise Error("Codex hook-trust preflight workspace must match current working directory")
    var input = Pipe()
    var output = Pipe()
    var args = project_app_server_config_args(runtime_args, True)
    args.append("app-server")
    args.append("--stdio")
    var child = _spawn_app_server(
        binary,
        args,
        environment,
        input.fd_in.value().value,
        output.fd_out.value().value,
    )
    input.set_output_only()
    output.set_input_only()
    try:
        _set_nonblocking(input.fd_out.value().value)
        _set_nonblocking(output.fd_in.value().value)
        var session = HookTrustSession(workspace)
        _run_session(session, input, output)
        var legacy = session.legacy
        _stop_child(child)
        return legacy
    except error:
        try:
            _stop_child(child)
        except cleanup_error:
            raise Error(String(error) + "; cleanup failed: " + String(cleanup_error))
        raise
