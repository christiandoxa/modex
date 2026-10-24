from std.collections import List, Optional, Span
from std.io import FileHandle, RawFileDescriptor
from std.os import stat
from std.sys._libc_errno import ErrNo, get_errno

comptime FOLLOW_MAX_PENDING_BYTES = 1024 * 1024
comptime FOLLOW_MAX_LINE_BYTES = 2 * 1024 * 1024
comptime FOLLOW_READ_BYTES = 1024 * 1024


struct FollowedLog(Movable):
    var offset: UInt64
    var pending: List[UInt8]
    var file: Optional[FileHandle]
    var device: UInt64
    var inode: UInt64
    var has_identity: Bool

    def __init__(out self, offset: UInt64 = 0):
        self.offset = offset
        self.pending = []
        self.file = Optional[FileHandle]()
        self.device = 0
        self.inode = 0
        self.has_identity = False

    def __init__(out self, path: String) raises:
        self.offset = 0
        self.pending = []
        self.file = Optional[FileHandle]()
        self.device = 0
        self.inode = 0
        self.has_identity = False
        try:
            var info = stat(path)
            if (info.st_mode & 0o170000) == 0o100000:
                self.offset = UInt64(info.st_size)
        except:
            pass


def log_follow_gap(dropped: Int, reason: String) -> String:
    return "[log] runtime_log_gap dropped=" + String(dropped) + " reason=" + reason


def collect_new_followed_lines(path: String, mut state: FollowedLog) raises -> List[String]:
    var output = List[String]()
    var mode: Int
    var current_device: UInt64
    var current_inode: UInt64
    var current_size: UInt64
    try:
        var info = stat(path)
        mode = info.st_mode & 0o170000
        current_device = UInt64(info.st_dev)
        current_inode = UInt64(info.st_ino)
        current_size = UInt64(info.st_size)
    except:
        var errno = get_errno()
        if errno == ErrNo.ENOENT:
            state.file = Optional[FileHandle]()
            state.has_identity = False
            return output^
        raise Error("failed to inspect " + path + ": " + String(errno) + " (os error " + String(errno.value) + ")")
    if mode != 0o100000:
        state.file = Optional[FileHandle]()
        state.has_identity = False
        return output^

    var replace_file = not state.has_identity or state.device != current_device or state.inode != current_inode
    if replace_file:
        var had_file = state.has_identity
        try:
            state.file = Optional(open(path, "r"))
        except:
            var errno = get_errno()
            raise Error("failed to open " + path + ": " + String(errno) + " (os error " + String(errno.value) + ")")
        state.device = current_device
        state.inode = current_inode
        state.has_identity = True
        if had_file:
            state.offset = 0
            state.pending.clear()
    var opened = stat("/proc/self/fd/" + String(RawFileDescriptor(state.file.value()).value))
    if UInt64(opened.st_dev) != state.device or UInt64(opened.st_ino) != state.inode:
        state.file = Optional[FileHandle]()
        state.has_identity = False
        return output^
    var file_len = current_size
    if file_len < state.offset:
        state.offset = 0
        state.pending.clear()
    if file_len <= state.offset:
        return output^

    _ = state.file.value().seek(Int(state.offset))
    var bytes = state.file.value().read_bytes(FOLLOW_READ_BYTES)
    state.offset += UInt64(len(bytes))
    for byte in bytes:
        state.pending.append(byte)

    var start = 0
    var dropped_lines = 0
    var kept = List[String]()
    for index in range(len(state.pending)):
        if state.pending[index] == 10:
            var line = String(from_utf8_lossy=Span(state.pending)[start:index])
            var line_size = line.byte_length() + 1
            if line_size > FOLLOW_MAX_LINE_BYTES:
                dropped_lines += 1
            else:
                if line.byte_length() > 0 and state.pending[index - 1] == 13:
                    line = String(from_utf8_lossy=Span(state.pending)[start:index - 1])
                kept.append(line)
            start = index + 1
    if start > 0:
        var remaining = List[UInt8]()
        for index in range(start, len(state.pending)):
            remaining.append(state.pending[index])
        state.pending = remaining^
    if dropped_lines > 0:
        output.append(log_follow_gap(dropped_lines, "oversized_line"))
    for line in kept:
        output.append(line)
    if len(state.pending) > FOLLOW_MAX_PENDING_BYTES:
        state.pending.clear()
        output.append(log_follow_gap(1, "oversized_partial_line"))
    return output^
