"""Bounded discovery and selection of files watched by log followers."""

from std.collections import List, Span
from std.os import stat

from .logs import collect_files, file_newer
from .paths import shared_root

comptime MAX_FOLLOWED_LOG_FILES = 32
comptime SOURCE_RESERVATION = 16


@fieldwise_init
struct FollowCandidate(Copyable):
    var path: String
    var source: Int
    var seconds: Int
    var nanoseconds: Int


def recent_session_log_paths(root: String) raises -> List[String]:
    var paths = List[String]()
    collect_files(shared_root(root) + "/sessions", paths, ".jsonl")
    sort(Span(paths), lambda (left: String, right: String) -> Bool: file_newer(left, right, True))
    while len(paths) > MAX_FOLLOWED_LOG_FILES:
        _ = paths.pop()
    return paths^


def bounded_follow_paths(
    runtime: List[String], sessions: List[String]
) raises -> Tuple[List[String], List[String]]:
    var candidates = List[FollowCandidate]()
    append_candidates(candidates, runtime, 0)
    append_candidates(candidates, sessions, 1)

    sort(Span(candidates), candidate_newer)
    var selected = List[FollowCandidate]()
    var runtime_count = 0
    var session_count = 0
    if len(runtime) > 0 and len(sessions) > 0:
        for candidate in candidates:
            if candidate.source == 0 and runtime_count < SOURCE_RESERVATION:
                selected.append(FollowCandidate(String(candidate.path), candidate.source, candidate.seconds, candidate.nanoseconds))
                runtime_count += 1
            elif candidate.source == 1 and session_count < SOURCE_RESERVATION:
                selected.append(FollowCandidate(String(candidate.path), candidate.source, candidate.seconds, candidate.nanoseconds))
                session_count += 1
    for candidate in candidates:
        if len(selected) >= MAX_FOLLOWED_LOG_FILES:
            break
        if not contains_candidate(selected, candidate.source, candidate.path):
            selected.append(FollowCandidate(String(candidate.path), candidate.source, candidate.seconds, candidate.nanoseconds))

    var selected_runtime = List[String]()
    for path in runtime:
        if contains_candidate(selected, 0, path):
            selected_runtime.append(String(path))
    var selected_sessions = List[String]()
    for path in sessions:
        if contains_candidate(selected, 1, path):
            selected_sessions.append(String(path))
    return (selected_runtime^, selected_sessions^)


def append_candidates(mut candidates: List[FollowCandidate], paths: List[String], source: Int) raises:
    for path in paths:
        var seconds = 0
        var nanoseconds = 0
        try:
            var modified = stat(path).st_mtimespec
            seconds = modified.tv_sec
            nanoseconds = modified.tv_nsec
        except:
            pass
        if not contains_candidate(candidates, source, path):
            candidates.append(FollowCandidate(String(path), source, seconds, nanoseconds))


def candidate_newer(left: FollowCandidate, right: FollowCandidate) -> Bool:
    if left.seconds != right.seconds:
        return left.seconds > right.seconds
    if left.nanoseconds != right.nanoseconds:
        return left.nanoseconds > right.nanoseconds
    if left.path != right.path:
        return left.path < right.path
    return left.source < right.source


def contains_candidate(candidates: List[FollowCandidate], source: Int, path: String) -> Bool:
    for candidate in candidates:
        if candidate.source == source and candidate.path == path:
            return True
    return False
