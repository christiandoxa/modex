"""Detached runtime and transcript event streaming from bounded log files."""

from std.collections import List, Optional
from std.os import getenv, isatty
from std.sys import stderr
from std.time import perf_counter, sleep

from .log_follow import FollowedLog, collect_new_followed_lines, retain_followed_paths
from .log_follow_paths import bounded_follow_paths, recent_session_log_paths
from .log_operational import operational_event
from .log_redaction import redact_log_text
from .log_text import trim_unicode
from .log_time import local_log_timestamp
from .log_transcript import transcript_events
from .log_upstream_follow import print_upstream, require_file_log_sources
from .logs import LogEvent, RUNTIME_TAIL_BYTES, RuntimeRecord, TokenEvent, UpstreamEvent, event_label, latest_transcript, read_tail, recent_runtime_log_paths, render_event, render_token, timestamp_wins, token_event, upstream_event
from .paths import ensure_app_root


def stream_payload_event(record: RuntimeRecord) -> Optional[LogEvent]:
    if not record.envelope or record.event != "stream_payload" or not record.has("source"):
        return None
    var text = record.field("stream") if record.has("stream") else record.field("message")
    var source = record.field("source")
    if not trim_unicode(source) or not trim_unicode(text):
        return None
    return LogEvent(local_log_timestamp(record.timestamp if record.timestamp_present else "-"), redact_log_text(source), redact_log_text(text))


def print_stream_event(event: LogEvent, json: Bool) raises:
    if json:
        print(event.json())
    elif event.source != "load":
        print(render_event(event.timestamp, event_label(event.source), event.text), end="")


def print_stream_token(event: TokenEvent, json: Bool) raises:
    print(event.json() + "\n" if json else render_token(event), end="")


def session_stream_paths(root: String) -> List[String]:
    try:
        return recent_session_log_paths(root)
    except:
        return List[String]()


def initial_stream_events(runtime: List[String], sessions: List[String], json: Bool) raises:
    var found = False
    for path in sessions:
        var event: Optional[LogEvent]
        try:
            event = latest_transcript(path)
        except:
            continue
        if event:
            print_stream_event(event.value(), json)
            found = True
            break
    var stream = Optional[LogEvent]()
    var upstream = Optional[UpstreamEvent]()
    var token = Optional[TokenEvent]()
    for path in runtime:
        var contents: String
        try:
            contents = read_tail(path, RUNTIME_TAIL_BYTES)
        except:
            continue
        for line in contents.split("\n"):
            var record = RuntimeRecord(String(line))
            var stream_item = stream_payload_event(record)
            if stream_item and (not stream or timestamp_wins(stream.value().timestamp, stream_item.value().timestamp)):
                stream = stream_item^
            var upstream_item = upstream_event(record)
            if upstream_item and (not upstream or timestamp_wins(upstream.value().timestamp, upstream_item.value().timestamp)):
                upstream = upstream_item^
            var token_item = token_event(record)
            if token_item and (not token or timestamp_wins(token.value().timestamp, token_item.value().timestamp)):
                token = token_item^
    if stream:
        print_stream_event(stream.value(), json)
        found = True
    if upstream:
        print_upstream(upstream.value(), json)
        found = True
    if token:
        print_stream_token(token.value(), json)
        found = True
    if not found:
        print("Waiting for transcript, upstream payload, or token events.", file=stderr)


def print_runtime_stream_lines(lines: List[String], json: Bool) raises:
    for line in lines:
        var record = RuntimeRecord(line)
        var operational = operational_event(record)
        if operational:
            print_stream_event(operational.value(), json)
        var stream = stream_payload_event(record)
        if stream:
            print_stream_event(stream.value(), json)
        var upstream = upstream_event(record)
        if upstream:
            print_upstream(upstream.value(), json)
        var token = token_event(record)
        if token:
            print_stream_token(token.value(), json)


def print_transcript_stream_lines(lines: List[String], json: Bool) raises:
    var previous = Optional[LogEvent]()
    for line in lines:
        for projected in transcript_events(line):
            var event = LogEvent(local_log_timestamp(projected[0]), projected[1], projected[2])
            if previous and previous.value().timestamp == event.timestamp and previous.value().source == event.source and previous.value().text == event.text:
                continue
            if json:
                print(event.json())
            else:
                print(render_event(event.timestamp, event_label(event.source), event.text), end="")
            previous = event^


def follow_stream(json: Bool) raises:
    if not json and (isatty(2) or (isatty(0) and isatty(1) and getenv("NO_COLOR", "\0") == "\0")):
        raise Error("log stream terminal rendering is not implemented")
    var root = ensure_app_root()
    require_file_log_sources(root)
    var runtime = recent_runtime_log_paths(root)
    var sessions = session_stream_paths(root)
    initial_stream_events(runtime, sessions, json)
    var runtime_paths = List[String]()
    var session_paths = List[String]()
    var runtime_states = List[FollowedLog]()
    var session_states = List[FollowedLog]()
    var selected = bounded_follow_paths(runtime, sessions)
    retain_followed_paths(runtime_paths, runtime_states, selected[0].copy())
    retain_followed_paths(session_paths, session_states, selected[1].copy())
    var runtime_refreshed = perf_counter()
    var session_refreshed = runtime_refreshed
    while True:
        require_file_log_sources(root)
        var now = perf_counter()
        if now - runtime_refreshed >= 2.0:
            runtime = recent_runtime_log_paths(root)
            runtime_refreshed = now
        if now - session_refreshed >= 10.0:
            sessions = session_stream_paths(root)
            session_refreshed = now
        selected = bounded_follow_paths(runtime, sessions)
        retain_followed_paths(runtime_paths, runtime_states, selected[0].copy())
        retain_followed_paths(session_paths, session_states, selected[1].copy())
        for index in range(len(runtime_paths)):
            print_runtime_stream_lines(collect_new_followed_lines(runtime_paths[index], runtime_states[index]), json)
        for index in range(len(session_paths)):
            print_transcript_stream_lines(collect_new_followed_lines(session_paths[index], session_states[index]), json)
        sleep(0.1)
