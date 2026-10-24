"""Spawn an absolute executable path with a complete explicit environment.

The pinned stdlib spawn wrapper exposes no file actions, so this module does
not redirect child stdin, stdout, or stderr.
The returned standard Process waits for the child when destroyed.
Other inheritable descriptors retain the standard POSIX spawn behavior.
"""

from std.collections import List, Optional
from std.ffi import c_pid_t, CStringSpan
from std.sys import CompilationTarget
from std.sys._libc import posix_spawnp
from std.os.process import Process


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
