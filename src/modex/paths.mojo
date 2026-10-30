from std.os import getenv, getuid, lstat, makedirs, stat
from std.os.path import exists, realpath
from std.pathlib import Path, cwd
from std.sys._libc_errno import ErrNo, get_errno


def absolute_path(path: String) raises -> String:
    if path.startswith("/"):
        return path
    return String(cwd()) + "/" + path


def app_root() raises -> String:
    return absolute_path(getenv("PRODEX_HOME", String(Path.home()) + "/.prodex"))


def app_root_is_absent() raises -> Bool:
    var configured_root = app_root()
    var root_length = configured_root.byte_length()
    while root_length > 1 and configured_root.as_bytes()[root_length - 1] == 47:
        root_length -= 1
    var root = String(configured_root)
    if root_length < configured_root.byte_length():
        root = String(configured_root[byte=0:root_length])
    if root == "/":
        return False
    var parts = root.split("/")
    var leaf = len(parts) - 1
    while leaf > 0 and not parts[leaf]:
        leaf -= 1
    if leaf == 0:
        return False
    var parent = String("/")
    for index in range(1, leaf):
        var part = String(parts[index])
        if not part:
            continue
        if parent != "/":
            parent += "/"
        parent += part
    var resolved_parent: String
    try:
        resolved_parent = realpath(parent)
        var parent_info = stat(resolved_parent)
        if (parent_info.st_mode & 0o170000) != 0o040000:
            return False
    except:
        return False
    var entry = resolved_parent
    if entry != "/":
        entry += "/"
    entry += String(parts[leaf])
    try:
        _ = lstat(entry)
        return False
    except:
        return get_errno() == ErrNo.ENOENT


def ensure_app_root() raises -> String:
    var root = app_root()
    if exists(root):
        var info = lstat(root)
        # shortcut: Mojo stdlib cannot repair existing root permissions; add repair when chmod is available.
        if (info.st_mode & 0o170000) != 0o040000 or info.st_uid != getuid() or (info.st_mode & 0o077) != 0:
            raise Error("secure application-directory permission repair is not implemented")
    else:
        makedirs(root, mode=0o700, exist_ok=True)
    return root^


def shared_root(root: String) raises -> String:
    var path = getenv("PRODEX_SHARED_CODEX_HOME", String(Path.home()) + "/.codex")
    if path.startswith("/"):
        return path^
    return root + "/" + path


def comparable_path(path: String) -> String:
    if "\x00" in path:
        return path
    try:
        return realpath(path)
    except:
        var result = String("/" if path.startswith("/") else "")
        for part in path.split("/"):
            if not part or part == ".":
                continue
            if result and result != "/":
                result += "/"
            result += part
        return result^
