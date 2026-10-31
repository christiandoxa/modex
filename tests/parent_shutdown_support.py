"""Process fixture shared by active and historical parent-shutdown tests."""

import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

from test_local_rewrite import SYNTHETIC_API_KEY, serving

CLIENT = r'''
import http.client, json, os, pathlib, sys, time
from urllib.parse import urlsplit
args = sys.argv[1:]
capture = pathlib.Path(os.environ["MODEX_LAUNCH_CAPTURE"])
def save(value):
    value["script_argv0"] = sys.argv[0]
    with capture.open("a") as handle: handle.write(json.dumps(value) + "\n")
if args == ["--version"]:
    print("codex-cli 0.216.0")
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request: continue
        save({"kind": "request", "method": request["method"], "params": request.get("params")})
        print(json.dumps({"id": request["id"], "result": {"data": []}}), flush=True)
        if request["id"] == 4: time.sleep(30)
    raise SystemExit(0)
home = pathlib.Path(os.environ["CODEX_HOME"])
auth = json.loads((home / "auth.json").read_text())
authorization = "Bearer " + auth["OPENAI_API_KEY"]
config = {}
for index, arg in enumerate(args[:-1]):
    if arg == "-c":
        key, value = args[index + 1].split("=", 1)
        try: value = json.loads(value)
        except ValueError: pass
        config[key] = value
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + "/responses")
previous = None
for turn in json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text()):
    path = turn.pop("_path", target.path)
    raw_body = turn.pop("_raw_body", None)
    headers = {"Content-Type": "application/json", "Authorization": authorization,
               **turn.pop("_headers", {})}
    started = int(time.time())
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
    body = raw_body.encode() if raw_body is not None else json.dumps(turn, separators=(",", ":")).encode()
    connection.request("POST", path, body, headers)
    response = connection.getresponse()
    payload = response.read()
    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),
          "body": payload.hex(), "started": started, "finished": int(time.time())})
    connection.close()
    if response.status == 200:
        if "text/event-stream" in response.getheader("Content-Type", ""):
            for line in payload.splitlines():
                if line.startswith(b"data: "):
                    event = json.loads(line[6:])
                    previous = event.get("response", {}).get("id", previous)
        else:
            previous = json.loads(payload)["id"]
print("synthetic-continuation-complete")
'''

def _observe_parent_shutdown(
    binary, request, reply, pipeline_body_bytes=1048576, pipeline_head_bytes=None,
    hold_client_until_shutdown=False,
):
    client = CLIENT
    loop_marker = '\nfor turn in json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text()):\n'
    client_head, found_loop, client_loop = client.partition(loop_marker)
    if not found_loop:
        raise AssertionError("synthetic client could not isolate its sequential request loop")
    payload_block = (
        '    payload = response.read()\n'
        '    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),\n'
        '          "body": payload.hex(), "started": started, "finished": int(time.time())})'
    )
    read_and_save = (
        '    payload = bytearray()\n'
        '    while b"event: response.failed\\r\\n" not in payload:\n'
        '        piece = response.read1(4096)\n'
        '        if not piece: break\n'
        '        payload.extend(piece)\n'
        '    save({"kind":"held","body":bytes(payload).hex()})\n'
        '    release = os.environ.get("MODEX_PARENT_SHUTDOWN_RELEASE")\n'
        '    if release:\n'
        '        save({"kind":"shutdown_hold"})\n'
        '        while not pathlib.Path(release).exists(): time.sleep(0.01)\n'
        '    try:\n'
        '        while True:\n'
        '            piece = response.read1(4096)\n'
        '            if not piece: break\n'
        '    except Exception as error:\n'
        '        save({"kind":"body_error","error":type(error).__name__ + ": " + str(error)})\n'
        '    payload = bytes(payload)\n'
        '    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),\n'
        '          "body": payload.hex(), "started": started, "finished": int(time.time())})'
    )
    if payload_block not in client_loop:
        raise AssertionError("synthetic client could not capture held response bodies")
    client_loop = client_loop.replace(payload_block, read_and_save, 1)
    marker = "    response = connection.getresponse()"
    pipeline = (
        f'    pipeline_body = b"x" * {pipeline_body_bytes}\n'
        '    pipeline = (\n'
        '        b"POST " + target.path.encode() + b" HTTP/1.1\\r\\n"\n'
        '        + b"Host: " + target.hostname.encode() + b":" + str(target.port).encode() + b"\\r\\n"\n'
        '        + b"Content-Type: application/json\\r\\nContent-Length: 1048576\\r\\n"\n'
        '        + b"Connection: keep-alive\\r\\n\\r\\n" + pipeline_body\n'
        '    )\n'
        + (f'    pipeline = pipeline[:{pipeline_head_bytes}]\n' if pipeline_head_bytes is not None else "")
        + '    connection.sock.sendall(pipeline)\n'
        + '    pipeline_head = pipeline[:len(pipeline) - len(pipeline_body)]\n'
        + '    save({"kind":"pipelined","bytes":len(pipeline_body),"wire_bytes":len(pipeline),'
        + '"head_hex":pipeline_head.hex(),"write_open":True})\n'
    )
    if marker not in client_loop:
        raise AssertionError("synthetic client could not locate the sequential response head")
    client_loop = client_loop.replace(marker, pipeline + marker, 1)
    client = client_head + loop_marker + client_loop
    if (
        client == CLIENT or '"kind":"held"' not in client
        or '"kind":"pipelined"' not in client
    ):
        raise AssertionError("synthetic client could not hold the stream open")
    with tempfile.TemporaryDirectory(prefix="modex-parent-shutdown-") as temporary:
        root = Path(temporary)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        release_path = root / "release-client" if hold_client_until_shutdown else None
        (root / "state/update-check.json").write_text(
            '{"source":"GitHub","latest_version":"0.439.2","checked_at":4102444800}'
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + client)
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        turns_file = root / "turns.json"
        turns_file.write_text(json.dumps([request]))
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"),
            "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex),
            "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered",
            "MODEX_CONTINUATION_TURNS_FILE": str(turns_file),
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "XDG_CONFIG_HOME": str(root / "home"),
            "XDG_CACHE_HOME": str(root / "home"),
            "XDG_DATA_HOME": str(root / "home"),
        }
        if release_path is not None:
            environment["MODEX_PARENT_SHUTDOWN_RELEASE"] = str(release_path)
        with serving([reply]) as upstream:
            process = subprocess.Popen(
                [
                    str(binary), "super", "--provider", "deepseek", "--api-key",
                    SYNTHETIC_API_KEY, "--base-url",
                    f"http://127.0.0.1:{upstream.server_port}/v1", "--model",
                    "deepseek-chat", "--no-presidio", "--no-sub-agent",
                    "--skip-quota-check", "exec", "--", "synthetic",
                ],
                cwd=root / "work", env=environment,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            children = {}

            def remember_children():
                try:
                    values = Path(
                        f"/proc/{process.pid}/task/{process.pid}/children"
                    ).read_text().split()
                except FileNotFoundError:
                    return
                for value in values:
                    pid = int(value)
                    if pid in children:
                        continue
                    try:
                        children[pid] = os.pidfd_open(pid)
                    except ProcessLookupError:
                        pass

            held = False
            client_waiting_for_shutdown = False
            shutdown_sent = False
            parent_alive_before_shutdown = False
            parent_timed_out = False
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    remember_children()
                    try:
                        rows = [
                            json.loads(line) for line in capture.read_text().splitlines()
                            if line
                        ] if capture.exists() else []
                    except json.JSONDecodeError:
                        rows = []
                    client_waiting_for_shutdown = any(
                        row.get("kind") == "shutdown_hold" for row in rows
                    )
                    if any(row.get("kind") == "held" for row in rows) and (
                        not hold_client_until_shutdown or client_waiting_for_shutdown
                    ):
                        held = True
                        break
                    time.sleep(0.02)
                remember_children()
                if held:
                    parent_alive_before_shutdown = process.poll() is None
                    if parent_alive_before_shutdown:
                        try:
                            process.send_signal(signal.SIGTERM)
                            shutdown_sent = True
                        except ProcessLookupError:
                            pass
                        finally:
                            if release_path is not None:
                                release_path.touch()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    parent_timed_out = True
                    process.kill()
                    process.wait(timeout=2)
                deadline = time.monotonic() + 2
                child_handles = list(children.items())
                alive_children = child_handles.copy()
                while time.monotonic() < deadline:
                    alive_children = [
                        (pid, fd) for pid, fd in child_handles
                        if not select.select([fd], [], [], 0)[0]
                    ]
                    if not alive_children:
                        break
                    time.sleep(0.02)
                for _, fd in alive_children:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if alive_children:
                    time.sleep(0.05)
                try:
                    rows = [
                        json.loads(line) for line in capture.read_text().splitlines()
                        if line
                    ] if capture.exists() else []
                except json.JSONDecodeError:
                    rows = []
                upstream_client_closed = (
                    upstream.client_closed.wait(timeout=2) if reply.get("hold_open") else None
                )
                return {
                    "parent_returncode": process.returncode,
                    "shutdown_sent": shutdown_sent,
                    "client_waiting_for_shutdown": client_waiting_for_shutdown,
                    "parent_alive_before_shutdown": parent_alive_before_shutdown,
                    "parent_timed_out": parent_timed_out,
                    "children_alive_after_2s": [pid for pid, _ in alive_children],
                    "upstream_client_closed": upstream_client_closed,
                    "upstream_hold_timed_out": upstream.hold_timed_out.is_set(),
                    "held": held or any(row.get("kind") == "held" for row in rows),
                    "held_records": [row for row in rows if row.get("kind") == "held"],
                    "pipelined_records": [row for row in rows if row.get("kind") == "pipelined"],
                    "body_errors": [row for row in rows if row.get("kind") == "body_error"],
                    "responses": [row for row in rows if row.get("kind") == "response"],
                }
            finally:
                if release_path is not None:
                    release_path.touch(exist_ok=True)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
                for fd in children.values():
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finally:
                        os.close(fd)
