"""Follow processed upstream payloads from bounded runtime log files."""

from std.collections import List
from std.os import getenv, isatty, listdir
from std.sys import stderr
from std.time import perf_counter, sleep

from .log_follow import FollowedLog, collect_new_followed_lines, retain_followed_paths
from .logs import RUNTIME_TAIL_BYTES, RuntimeRecord, UpstreamEvent, read_tail, recent_runtime_log_paths, render_upstream, timestamp_wins, upstream_event
from .paths import ensure_app_root


def require_file_log_sources(root: String) raises:
    for name in listdir(root):
        if name.startswith("runtime-broker-") and name.endswith(".json"):
            raise Error("live runtime log sources are not implemented")


def print_upstream(event: UpstreamEvent, json: Bool) raises:
    print(event.json() + "\n" if json else render_upstream(event), end="")


def follow_upstream(json: Bool) raises:
    if not json and (isatty(2) or (isatty(0) and isatty(1) and getenv("NO_COLOR", "\0") == "\0")):
        raise Error("upstream terminal rendering is not implemented")
    var root = ensure_app_root()
    require_file_log_sources(root)
    var paths = recent_runtime_log_paths(root)
    var latest = Optional[UpstreamEvent]()
    for path in paths:
        var contents: String
        try:
            contents = read_tail(path, RUNTIME_TAIL_BYTES)
        except:
            continue
        for line in contents.split("\n"):
            var event = upstream_event(RuntimeRecord(String(line)))
            if event and (not latest or timestamp_wins(latest.value().timestamp, event.value().timestamp)):
                latest = event^
    if latest:
        print_upstream(latest.value(), json)
    else:
        print("Waiting for processed upstream payload events...", file=stderr)

    var states = List[FollowedLog]()
    for path in paths:
        states.append(FollowedLog(path))
    var refreshed = perf_counter()
    while True:
        require_file_log_sources(root)
        var now = perf_counter()
        if now - refreshed >= 2.0:
            var discovered = recent_runtime_log_paths(root)
            retain_followed_paths(paths, states, discovered^)
            refreshed = now
        for index in range(len(paths)):
            var lines = collect_new_followed_lines(paths[index], states[index])
            for line in lines:
                var event = upstream_event(RuntimeRecord(line))
                if event:
                    print_upstream(event.value(), json)
        sleep(0.1)
