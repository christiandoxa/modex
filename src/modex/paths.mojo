from std.os import getenv
from std.os.path import realpath
from std.pathlib import Path, cwd


def absolute_path(path: String) raises -> String:
    if path.startswith("/"):
        return path
    return String(cwd()) + "/" + path


def app_root() raises -> String:
    return absolute_path(getenv("PRODEX_HOME", String(Path.home()) + "/.prodex"))


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
