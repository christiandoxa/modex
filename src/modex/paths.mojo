from std.os import getenv, getuid, lstat, makedirs
from std.os.path import exists, realpath
from std.pathlib import Path, cwd


def absolute_path(path: String) raises -> String:
    if path.startswith("/"):
        return path
    return String(cwd()) + "/" + path


def app_root() raises -> String:
    return absolute_path(getenv("PRODEX_HOME", String(Path.home()) + "/.prodex"))


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
