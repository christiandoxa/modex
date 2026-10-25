"""Spawn an absolute executable path with a complete explicit environment.

The pinned stdlib spawn wrapper exposes no file actions. Startup-only stdio
redirection below temporarily changes parent descriptors and restores them.
The returned standard Process waits for the child when destroyed.
Other inheritable descriptors retain the standard POSIX spawn behavior.
"""

from std.collections import List, Optional
from std.ffi import c_pid_t, CStringSpan, ErrNo, get_errno
from std.sys import CompilationTarget
from std.sys._libc import close, dup, dup2, fcntl, FcntlCommands, FcntlFDFlags, posix_spawnp
from std.os.process import Process, ProcessStatus
from std.time import perf_counter, sleep


@fieldwise_init
struct ProcessWaitOutcome(Copyable, ImplicitlyCopyable, Movable):
    var status: ProcessStatus
    var timed_out: Bool


def spawn_with_env(path: String, args: List[String], env: List[String]) raises -> Process:
    comptime assert CompilationTarget.is_linux() or CompilationTarget.is_macos(), "POSIX spawn is supported only on Linux and macOS"
    if not path.startswith("/") or "\0" in path:
        raise Error("executable path must be absolute and NUL-free")

    var stored = List[String]()
    stored.append(path)
    for i in range(len(args)):
        stored.append(args[i])
    for i in range(len(env)):
        stored.append(env[i])
    # Keep storage fixed while argv/envp spans reference its strings.
    ref exe = stored[0]
    var argv = List[Optional[CStringSpan[ImmutAnyOrigin]]](length=len(args) + 2, fill={})
    argv[0] = exe.as_c_string_span().as_unsafe_any_origin()
    for i in range(len(args)):
        ref arg = stored[i + 1]
        if "\0" in arg:
            raise Error("invalid process argument")
        argv[i + 1] = arg.as_c_string_span().as_unsafe_any_origin()

    var envp = List[Optional[CStringSpan[ImmutAnyOrigin]]](length=len(env) + 1, fill={})
    for i in range(len(env)):
        ref entry = stored[len(args) + 1 + i]
        if entry.find("=") <= 0 or "\0" in entry:
            raise Error("invalid child environment entry")
        envp[i] = entry.as_c_string_span().as_unsafe_any_origin()

    var pid: c_pid_t = 0
    var status = posix_spawnp(
        Pointer(to=pid), exe.as_c_string_span(), argv.unsafe_ptr(), rebind[Pointer[Optional[CStringSpan[ImmutAnyOrigin]], ImmutAnyOrigin]](envp.unsafe_ptr())
    )
    if status != 0:
        raise Error("process spawn failed with errno " + String(status))
    return Process(child_pid=pid)


def _duplicate_onto(source: Int32, target: Int32) -> Bool:
    while dup2(source, target) < 0:
        if get_errno() != ErrNo.EINTR:
            return False
    return True


struct _SavedStdio:
    var input: Int32
    var output: Int32
    var input_flags: Int32
    var output_flags: Int32
    var error: Int32
    var error_flags: Int32

    def __init__(out self, save_stderr: Bool) raises:
        self.input = -1
        self.output = -1
        self.error = -1
        self.error_flags = 0
        self.input_flags = fcntl(0, FcntlCommands.F_GETFD, 0)
        self.output_flags = fcntl(1, FcntlCommands.F_GETFD, 0)
        if self.input_flags < 0 or self.output_flags < 0:
            raise Error("stdio spawn requires open parent stdin and stdout")
        self.input = dup(0)
        if self.input < 0:
            raise Error("failed to save parent stdin")
        if fcntl(self.input, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
            _ = close(self.input)
            self.input = -1
            raise Error("failed to protect saved parent stdin")
        self.output = dup(1)
        if self.output < 0:
            _ = close(self.input)
            self.input = -1
            raise Error("failed to save parent stdout")
        if fcntl(self.output, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
            _ = close(self.input)
            _ = close(self.output)
            self.input = -1
            self.output = -1
            raise Error("failed to protect saved parent stdout")
        if save_stderr:
            self.error_flags = fcntl(2, FcntlCommands.F_GETFD, 0)
            self.error = dup(2)
            if self.error_flags < 0 or self.error < 0 or fcntl(self.error, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
                _ = close(self.input)
                _ = close(self.output)
                if self.error >= 0:
                    _ = close(self.error)
                self.input = -1
                self.output = -1
                self.error = -1
                raise Error("failed to save and protect parent stderr")

    def restore(mut self) -> Bool:
        var input_ok = _duplicate_onto(self.input, 0)
        var output_ok = _duplicate_onto(self.output, 1)
        var input_flags_ok = fcntl(0, FcntlCommands.F_SETFD, self.input_flags) == 0
        var output_flags_ok = fcntl(1, FcntlCommands.F_SETFD, self.output_flags) == 0
        var error_ok = True
        if self.error >= 0:
            error_ok = _duplicate_onto(self.error, 2)
            var flags_ok = fcntl(2, FcntlCommands.F_SETFD, self.error_flags) == 0
            error_ok = error_ok and flags_ok
        return input_ok and output_ok and input_flags_ok and output_flags_ok and error_ok

    def __deinit__(deinit self):
        if self.input >= 0:
            _ = close(self.input)
        if self.output >= 0:
            _ = close(self.output)
        if self.error >= 0:
            _ = close(self.error)


def spawn_with_env_stdio(path: String, args: List[String], env: List[String], stdin_fd: Int32, stdout_fd: Int32, stderr_fd: Int32 = -1) raises -> Process:
    """Spawn through two pipes before any parent background work or concurrent I/O.

    Both supplied descriptors must be above stderr. Their owners must close the
    child ends after this call. Stderr remains inherited unless supplied.
    """
    # shortcut: parent stdio swaps require startup without concurrent I/O; replace with spawn file actions when stdlib exposes them.
    if stdin_fd <= 2 or stdout_fd <= 2:
        raise Error("stdio spawn requires separate pipe descriptors above stderr")
    if fcntl(stdin_fd, FcntlCommands.F_GETFD, 0) < 0 or fcntl(stdout_fd, FcntlCommands.F_GETFD, 0) < 0:
        raise Error("stdio spawn requires open child pipe descriptors")
    if stderr_fd != -1 and (stderr_fd <= 2 or fcntl(stderr_fd, FcntlCommands.F_GETFD, 0) < 0):
        raise Error("stdio spawn requires an open child stderr descriptor above stderr")
    var saved = _SavedStdio(stderr_fd != -1)
    var redirected = _duplicate_onto(stdin_fd, 0)
    redirected = _duplicate_onto(stdout_fd, 1) and redirected
    if stderr_fd != -1:
        redirected = _duplicate_onto(stderr_fd, 2) and redirected
    if not redirected:
        var restored = saved.restore()
        raise Error("failed to redirect child stdio" if restored else "failed to restore parent stdio")
    var child: Process
    try:
        child = spawn_with_env(path, args, env)
    except:
        if not saved.restore():
            raise Error("failed to restore parent stdio after process spawn failed")
        raise
    if not saved.restore():
        _ = child.kill()
        _ = child.wait()
        raise Error("failed to restore parent stdio after process spawn")
    return child^


def wait_or_kill(mut child: Process, timeout_ms: UInt64) raises -> ProcessWaitOutcome:
    if timeout_ms == 0:
        raise Error("process wait timeout must be positive")
    var deadline = perf_counter() + Float64(timeout_ms) / 1000.0
    while True:
        var status = child.poll()
        if status.has_exited():
            return ProcessWaitOutcome(status, False)
        var remaining = deadline - perf_counter()
        if remaining <= 0.0:
            break
        sleep(0.001 if remaining > 0.001 else remaining)

    var status = child.poll()
    if status.has_exited():
        return ProcessWaitOutcome(status, False)
    if not child.kill():
        status = child.poll()
        if status.has_exited():
            return ProcessWaitOutcome(status, False)
        raise Error("process timed out and direct child could not be terminated")
    return ProcessWaitOutcome(child.wait(), True)
