"""Pinned-release observations through real Super and isolated synthetic peers."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes, serving
from test_super_launch import CODEX


CLIENT = CODEX[:CODEX.index('passthrough = scenario')]
CLIENT += r'''
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + "/responses")
previous = None
if os.environ.get("MODEX_CONTINUATION_CONCURRENT") == "1":
    from concurrent.futures import ThreadPoolExecutor
    def request_turn(source_turn):
        turn = dict(source_turn)
        path = turn.pop("_path", target.path)
        method = turn.pop("_method", "POST")
        raw_body = turn.pop("_raw_body", None)
        headers = {"Content-Type": "application/json", "Authorization": authorization,
                   **turn.pop("_headers", {})}
        started = int(time.time())
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
        body = raw_body.encode() if raw_body is not None else json.dumps(turn, separators=(",", ":")).encode()
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        payload = response.read()
        result = {"kind": "response", "status": response.status, "headers": dict(response.getheaders()),
                  "body": payload.hex(), "started": started, "finished": int(time.time())}
        connection.close()
        return result
    with ThreadPoolExecutor(max_workers=len(json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text()))) as executor:
        for result in executor.map(request_turn, json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text())):
            save(result)
    followups_file = os.environ.get("MODEX_CONTINUATION_FOLLOWUPS_FILE")
    if followups_file:
        for source_turn in json.loads(pathlib.Path(followups_file).read_text()):
            turn = dict(source_turn)
            path = turn.pop("_path", target.path)
            method = turn.pop("_method", "POST")
            raw_body = turn.pop("_raw_body", None)
            headers = {"Content-Type": "application/json", "Authorization": authorization,
                       **turn.pop("_headers", {})}
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
            body = raw_body.encode() if raw_body is not None else json.dumps(turn, separators=(",", ":")).encode()
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            payload = response.read()
            save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),
                  "body": payload.hex(), "started": int(time.time()), "finished": int(time.time())})
            connection.close()
    print("synthetic-continuation-complete")
    raise SystemExit(0)
for turn in json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text()):
    path = turn.pop("_path", target.path)
    method = turn.pop("_method", "POST")
    raw_body = turn.pop("_raw_body", None)
    headers = {"Content-Type": "application/json", "Authorization": authorization,
               **turn.pop("_headers", {})}
    if turn.pop("use_guardian_parent", False):
        turn["client_metadata"] = {"parent_response_id": previous}
    if turn.pop("use_previous", False):
        turn["previous_response_id"] = previous
    started = int(time.time())
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
    body = raw_body.encode() if raw_body is not None else json.dumps(turn, separators=(",", ":")).encode()
    connection.request(method, path, body, headers)
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


def observe_turns(
    binary, turns, responses, *, base_path="/v1", idle_timeout_ms=None,
    lookahead_timeout_ms=None, api_keys=None, concurrent=False,
    followup_turns=None, shared_config=None, latest_version="0.439.2",
    base_scheme="http",
):
    with tempfile.TemporaryDirectory(prefix="modex-continuation-") as temporary:
        root = Path(temporary)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        if shared_config is not None:
            (root / "shared/config.toml").write_text(shared_config)
            (root / "shared/config.toml").chmod(0o600)
        (root / "state/update-check.json").write_text(
            json.dumps({"source": "GitHub", "latest_version": latest_version,
                        "checked_at": 4102444800}, separators=(",", ":"))
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + CLIENT)
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        turns_file = root / "turns.json"
        turns_file.write_text(json.dumps(turns))
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "MODEX_CONTINUATION_TURNS_FILE": str(turns_file),
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "MODEX_CONTINUATION_CONCURRENT": "1" if concurrent else "0",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        if idle_timeout_ms is not None:
            environment["PRODEX_RUNTIME_PROXY_STREAM_IDLE_TIMEOUT_MS"] = str(idle_timeout_ms)
        if lookahead_timeout_ms is not None:
            environment["PRODEX_RUNTIME_PROXY_SSE_LOOKAHEAD_TIMEOUT_MS"] = str(lookahead_timeout_ms)
        if api_keys is not None:
            environment["DEEPSEEK_API_KEYS"] = api_keys
        if followup_turns is not None:
            followups_file = root / "followups.json"
            followups_file.write_text(json.dumps(followup_turns))
            environment["MODEX_CONTINUATION_FOLLOWUPS_FILE"] = str(followups_file)
        response_fixtures = [dict(response) for response in responses]
        with serving(response_fixtures) as server:
            for response in server.responses:
                headers = response.get("response_headers")
                if headers:
                    response["response_headers"] = [
                        (name, value.replace("{upstream_port}", str(server.server_port)))
                        for name, value in headers
                    ]
            auth_args = ["--api-key", SYNTHETIC_API_KEY] if api_keys is None else []
            result = subprocess.run(
                [str(binary), "super", "--provider", "deepseek", *auth_args,
                 "--base-url", f"{base_scheme}://127.0.0.1:{server.server_port}{base_path}", "--model", "deepseek-chat",
                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                cwd=root / "work", env=environment, capture_output=True, timeout=45,
            )
            if result.returncode != 0 or b"synthetic-continuation-complete" not in result.stdout:
                records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
                records = [record for record in records if record["kind"] == "response"]
                raise AssertionError((result.returncode, result.stdout, result.stderr, records, server.records))
        records = [json.loads(line) for line in capture.read_text().splitlines()]
        return server.records, [record for record in records if record["kind"] == "response"]


def buffered_reply(index=0, **fields):
    return {"status": 200, "content_type": "application/json", "body": json_bytes({
        "id": f"synthetic-chat-{index}", "model": "deepseek-chat",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic reply"},
                     "finish_reason": "stop"}], **fields,
    })}


class DeepSeekContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"oracle does not match pinned release: {binary}")

    def test_same_origin_redirect_status_and_method_matrix_matches_releases(self):
        cases = ((301, "GET"), (302, "GET"), (303, "GET"), (307, "POST"), (308, "POST"))
        for status, expected_method in cases:
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(status=status, binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic redirect request"}],
                        [{"status": status, "content_type": "text/plain", "body": b"discarded redirect body",
                          "response_headers": [("Location", "redirected"), ("Content-Type", "text/plain")]},
                         buffered_reply(9)],
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([post["method"] for post in upstream], ["POST", expected_method])
                    self.assertEqual([post["path"] for post in upstream],
                                     ["/v1/chat/completions", "/v1/chat/redirected"])
                    self.assertEqual([post["headers"]["authorization"] for post in upstream],
                                     ["Bearer " + SYNTHETIC_API_KEY] * 2)
                    self.assertEqual([post["headers"]["accept"] for post in upstream],
                                     ["text/event-stream, application/json"] * 2)
                    self.assertEqual([post["headers"]["accept-encoding"] for post in upstream],
                                     ["identity"] * 2)
                    self.assertTrue(upstream[0]["body"])
                    if expected_method == "GET":
                        self.assertEqual(upstream[1]["body"], b"")
                        self.assertNotIn("content-length", upstream[1]["headers"])
                        self.assertNotIn("content-type", upstream[1]["headers"])
                    else:
                        self.assertEqual(upstream[1]["body"], upstream[0]["body"])
                        self.assertEqual(upstream[1]["headers"]["content-length"],
                                         str(len(upstream[0]["body"])))
                        self.assertEqual(upstream[1]["headers"]["content-type"], "application/json")
                    self.assertEqual(json.loads(bytes.fromhex(responses[0]["body"]))["id"],
                                     "synthetic-chat-9")

    def test_same_origin_absolute_redirect_matches_releases(self):
        redirect = {"status": 308, "content_type": "text/plain", "body": b"discarded",
                    "response_headers": [("Location", "http://127.0.0.1:{upstream_port}/v1/absolute?synthetic=1"),
                                         ("Content-Type", "text/plain")]}
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [{"model": "deepseek-chat", "input": "synthetic absolute redirect"}],
                    [redirect, buffered_reply(6)],
                )
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual([post["path"] for post in upstream],
                                 ["/v1/chat/completions", "/v1/absolute?synthetic=1"])
                self.assertEqual(upstream[1]["method"], "POST")
                self.assertEqual(upstream[1]["body"], upstream[0]["body"])
                self.assertEqual(upstream[1]["headers"]["authorization"],
                                 "Bearer " + SYNTHETIC_API_KEY)

    def test_redirect_without_location_and_nonredirect_3xx_are_preserved(self):
        cases = [
            {"status": 307, "content_type": "text/plain", "body": b"no Location"},
            *({"status": status, "content_type": "text/plain", "body": b"",
               "response_headers": [("Location", "redirected"), ("Content-Type", "text/plain")]}
              for status in (300, 304, 399)),
        ]
        for response in cases:
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(status=response["status"], binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary, [{"model": "deepseek-chat", "input": "synthetic unhandled 3xx"}],
                        [response],
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual([row["status"] for row in responses], [response["status"]])
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), response["body"])

    def test_unsupported_redirect_url_is_returned_without_following(self):
        location = "https://127.0.0.1:1/v1/redirected"
        upstream, responses = observe_turns(
            MODEX, [{"model": "deepseek-chat", "input": "synthetic unsupported redirect"}],
            [{"status": 307, "content_type": "text/plain", "body": b"unsupported origin",
             "response_headers": [("Location", location), ("Content-Type", "text/plain")] }],
        )
        self.assertEqual(len(upstream), 1)
        self.assertEqual([response["status"] for response in responses], [307])
        headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
        self.assertEqual(headers.get("location"), location)
        self.assertEqual(bytes.fromhex(responses[0]["body"]), b"unsupported origin")

    def test_relative_redirect_query_on_chat_path_matches_releases(self):
        turn = {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic chat redirect"}],
                "_path": "/v1/chat/completions"}
        redirect = {"status": 307, "content_type": "text/plain", "body": b"discarded",
                    "response_headers": [("Location", "../redirected?synthetic=1"),
                                         ("Content-Type", "text/plain")]}
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, [turn], [redirect, buffered_reply(4)])
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual([post["path"] for post in upstream],
                                 ["/v1/chat/completions", "/v1/redirected?synthetic=1"])
                self.assertEqual([post["method"] for post in upstream], ["POST", "POST"])
                self.assertEqual(upstream[1]["body"], upstream[0]["body"])
                self.assertEqual(upstream[1]["headers"]["authorization"],
                                 "Bearer " + SYNTHETIC_API_KEY)

    def test_redirect_limit_matches_releases(self):
        redirects = [{"status": 307, "content_type": "text/plain", "body": b"",
                      "response_headers": [("Location", "/v1/chat/completions"),
                                           ("Content-Type", "text/plain")]}
                     for _ in range(11)]
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [{"model": "deepseek-chat", "input": "synthetic redirect cycle"}], redirects,
                )
                self.assertEqual(len(upstream), 11)
                self.assertEqual([post["path"] for post in upstream],
                                 ["/v1/chat/completions"] * 11)
                self.assertEqual([response["status"] for response in responses], [502])
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"upstream request failed")

    def test_cross_origin_redirect_does_not_disclose_modex_request(self):
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                with serving([buffered_reply(9)]) as redirected_server:
                    location = f"http://127.0.0.1:{redirected_server.server_port}/v1/redirected"
                    redirect = {"status": 307, "content_type": "text/plain", "body": b"cross-origin response",
                                "response_headers": [("Location", location),
                                                     ("Content-Type", "text/plain")]}
                    upstream, responses = observe_turns(
                        binary, [{"model": "deepseek-chat", "input": "synthetic cross-origin body"}],
                        [redirect],
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["headers"]["authorization"],
                                     "Bearer " + SYNTHETIC_API_KEY)
                    if binary == MODEX:
                        self.assertEqual(redirected_server.records, [])
                        self.assertEqual([response["status"] for response in responses], [307])
                        headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
                        self.assertEqual(headers.get("location"), location)
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), b"cross-origin response")
                    else:
                        self.assertEqual(len(redirected_server.records), 1)
                        followed = redirected_server.records[0]
                        self.assertEqual(followed["method"], "POST")
                        self.assertEqual(followed["headers"].get("authorization"), None)
                        self.assertEqual(followed["body"], upstream[0]["body"])
                        self.assertEqual([response["status"] for response in responses], [200])

    def test_redirect_final_stream_is_the_only_committed_response(self):
        chunk = {"id": "synthetic-redirect-stream", "created": 42, "model": "deepseek-chat",
                 "choices": [{"index": 0, "delta": {"content": "redirected stream"}}]}
        first = {"status": 307, "content_type": "text/plain", "body": b"discarded redirect body",
                 "response_headers": [("Location", "redirected"), ("Content-Type", "text/plain")]}
        final = {"status": 200, "content_type": "text/event-stream",
                 "body": b"data: " + json_bytes(chunk) + b"\n\n" + b"data: [DONE]\n\n",
                 "chunked": True}
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [{"model": "deepseek-chat", "input": "synthetic stream redirect", "stream": True}],
                    [first, final],
                )
                self.assertEqual([post["path"] for post in upstream],
                                 ["/v1/chat/completions", "/v1/chat/redirected"])
                self.assertEqual([response["status"] for response in responses], [200])
                headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
                self.assertIn("text/event-stream", headers.get("content-type", ""))
                body = bytes.fromhex(responses[0]["body"])
                self.assertIn(b"redirected stream", body)
                self.assertNotIn(b"discarded redirect body", body)

    def test_api_key_cursor_matches_release_request_order(self):
        keys = "synthetic-key-a,synthetic-key-b"
        key_a = "Bearer synthetic-key-a"
        key_b = "Bearer synthetic-key-b"
        binaries = (ORACLE_01651, ORACLE, MODEX)

        invalid_route = [
            {"model": "deepseek-chat", "input": "synthetic invalid route", "_path": "/v1/unknown"},
            {"model": "deepseek-chat", "input": "synthetic after invalid route"},
        ]
        for binary in binaries:
            with self.subTest(binary=str(binary), case="invalid route"):
                posts, responses = observe_turns(
                    binary, invalid_route, [buffered_reply(), buffered_reply(1)], api_keys=keys,
                )
                self.assertEqual([response["status"] for response in responses], [404, 200])
                self.assertEqual([post["headers"]["authorization"] for post in posts], [key_a])

        malformed_json = [
            {"_path": "/v1/responses", "_raw_body": "{"},
            {"model": "deepseek-chat", "input": "synthetic after malformed JSON"},
        ]
        for binary in binaries:
            with self.subTest(binary=str(binary), case="malformed JSON"):
                posts, responses = observe_turns(
                    binary, malformed_json, [buffered_reply()], api_keys=keys,
                )
                self.assertEqual([response["status"] for response in responses], [502, 200])
                self.assertEqual([post["headers"]["authorization"] for post in posts], [key_b])

        malformed_chat_body = b'{"model":"deepseek-chat","messages":['
        malformed_chat = [
            {"_path": "/v1/chat/completions", "_raw_body": malformed_chat_body.decode()},
            {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic after malformed Chat JSON"}],
             "_path": "/v1/chat/completions"},
        ]
        for binary in binaries:
            with self.subTest(binary=str(binary), case="malformed Chat Completions JSON passthrough"):
                posts, responses = observe_turns(
                    binary, malformed_chat, [buffered_reply(), buffered_reply(1)], api_keys=keys,
                )
                self.assertEqual([response["status"] for response in responses], [200, 200])
                self.assertEqual([post["headers"]["authorization"] for post in posts], [key_a, key_b])
                self.assertEqual(posts[0]["body"], malformed_chat_body)

        bound_requests = (
            ("response", {}, {"use_previous": True}),
            ("session", {"session_id": "synthetic-bound-session"},
             {"session_id": "synthetic-bound-session"}),
            ("turn", {"_headers": {"x-codex-turn-state": "synthetic-bound-turn"}},
             {"_headers": {"x-codex-turn-state": "synthetic-bound-turn"}}),
        )
        for identity, first_identity, rejected_identity in bound_requests:
            turns = [
                {"model": "deepseek-chat", "input": "synthetic bound request", **first_identity},
                {"model": "deepseek-chat", "input": "synthetic rejected continuation", **rejected_identity},
                {"model": "deepseek-chat", "input": "synthetic after rejection"},
            ]
            for binary in binaries:
                with self.subTest(binary=str(binary), case=f"rejected {identity} continuation"):
                    posts, responses = observe_turns(
                        binary, turns, [buffered_reply(), buffered_reply(1)], api_keys=keys,
                    )
                    self.assertEqual([response["status"] for response in responses], [200, 503, 200])
                    self.assertEqual([post["headers"]["authorization"] for post in posts], [key_a, key_b])

        empty_search = {
            "model": "deepseek-chat", "input": "",
            "tools": [{"type": "web_search"}],
        }
        valid = {"model": "deepseek-chat", "input": "synthetic after empty search"}
        for mode, expected_statuses, expected_keys in (
            ("auto", [400, 200], [key_b]),
            ("anthropic", [400, 200], [key_b]),
            ("openai_chat", [200, 200], [key_a, key_b]),
        ):
            config = f'[deepseek]\nweb_search_mode = "{mode}"\n'
            for binary in binaries:
                with self.subTest(binary=str(binary), case=f"empty search {mode}"):
                    posts, responses = observe_turns(
                        binary, [empty_search, valid], [buffered_reply(), buffered_reply(1)],
                        api_keys=keys, shared_config=config,
                    )
                    self.assertEqual([response["status"] for response in responses], expected_statuses)
                    self.assertEqual([post["headers"]["authorization"] for post in posts], expected_keys)
                    if mode == "openai_chat":
                        self.assertTrue(all(post["path"].endswith("/chat/completions") for post in posts))

    def test_stream_precommit_idle_and_lookahead_deadlines_match_release(self):
        chunk = {"id": "synthetic-idle-chat", "created": 42, "model": "deepseek-chat",
                 "choices": [{"index": 0, "delta": {"content": "kept before idle"}}]}
        cases = [
            ("empty_idle_first", b"", 100, 500, 502, [], []),
            ("partial_idle_first", b"data: {", 100, 500, 200, ["response.failed"], []),
            ("comment_idle_first", b": synthetic\n\n", 100, 500, 200, ["response.failed"], []),
            ("hold_idle_first", b'data: {"type":"response.created"}\n\n', 100, 500,
             200, ["response.created", "response.failed"], []),
            ("text_idle_first", b"data: " + json_bytes(chunk) + b"\n\n", 100, 500, 200,
             ["response.created", "response.output_item.added", "response.output_text.delta",
              "response.failed"], ["kept before idle"]),
            ("empty_lookahead_first", b"", 500, 100, 200, ["response.failed"], []),
            ("partial_lookahead_first", b"data: {", 500, 100, 200, ["response.failed"], []),
        ]
        for name, body, idle, lookahead, status, types, deltas in cases:
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(case=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, [{"model": "deepseek-chat", "input": "synthetic idle", "stream": True}],
                        [{"status": 200, "content_type": "text/event-stream", "body": body,
                          "chunked": True, "hold_open": True}],
                        idle_timeout_ms=idle, lookahead_timeout_ms=lookahead,
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(responses[0]["status"], status)
                    payload = bytes.fromhex(responses[0]["body"])
                    if status == 502:
                        self.assertEqual(payload, b"upstream request failed")
                        continue
                    events = [json.loads(line[6:]) for line in payload.splitlines()
                              if line.startswith(b"data: ")]
                    self.assertEqual([event["type"] for event in events], types)
                    self.assertEqual([event["delta"] for event in events
                                      if event["type"] == "response.output_text.delta"], deltas)
                    error = events[-1]["response"]["error"]
                    self.assertEqual(error["code"], "provider_stream_error")
                    # Release idle errors can win or lose to the generic body-read path.
                    self.assertIn(error["message"], (
                        "error decoding response body", "runtime upstream stream idle timed out",
                    ))
                    if name == "text_idle_first" and binary == MODEX:
                        self.assertEqual(error["message"], "runtime upstream stream idle timed out")

    def test_prefetch_partial_idle_diagnostic_matches_releases(self):
        cases = (
            ("chat", {
                "model": "deepseek-chat", "input": "synthetic partial idle", "stream": True,
            }, None),
            ("native", {
                "model": "deepseek-chat", "input": "synthetic partial native idle", "stream": True,
                "tools": [{"type": "web_search_preview"}],
            }, '[deepseek]\nweb_search_mode = "anthropic"\n'),
        )
        for name, turn, shared_config in cases:
            messages = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(path=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, [turn],
                        [{"status": 200, "content_type": "text/event-stream", "body": b"data: {",
                          "chunked": True, "hold_open": True}],
                        idle_timeout_ms=100, lookahead_timeout_ms=500,
                        shared_config=shared_config,
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(responses[0]["status"], 200)
                    events = [json.loads(line[6:])
                              for line in bytes.fromhex(responses[0]["body"]).splitlines()
                              if line.startswith(b"data: ")]
                    self.assertEqual([event["type"] for event in events], ["response.failed"])
                    error = events[0]["response"]["error"]
                    self.assertEqual(error["code"], "provider_stream_error")
                    messages.append(error["message"])
            self.assertEqual(messages, ["error decoding response body"] * 3)

    def test_precommit_failure_does_not_bind_later_requests(self):
        identities = (
            {"session_id": "synthetic-session"},
            {"_headers": {"x-codex-turn-state": "synthetic-turn"}},
            {"previous_response_id": "synthetic-previous"},
        )
        for identity in identities:
            for binary in (ORACLE, MODEX):
                with self.subTest(identity=identity, binary=str(binary)):
                    turns = [{"model": "deepseek-chat", "input": "first", "stream": True, **identity},
                             {"model": "deepseek-chat", "input": "retry", **identity}]
                    replies = [{"status": 200, "content_type": "text/event-stream", "body": b"",
                                "chunked": True, "hold_open": True}, buffered_reply(created=42)]
                    posts, responses = observe_turns(
                        binary, turns, replies, idle_timeout_ms=100, lookahead_timeout_ms=500,
                    )
                    self.assertEqual([row["status"] for row in responses], [502, 200])
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), b"upstream request failed")
                    self.assertEqual(len(posts), 2)

        chunk = {"id": "synthetic-committed", "created": 42,
                 "choices": [{"index": 0, "delta": {"content": "accepted"}}]}
        turns = [{"model": "deepseek-chat", "input": "first", "stream": True,
                  "session_id": "synthetic-committed-session"},
                 {"model": "deepseek-chat", "input": "retry",
                  "session_id": "synthetic-committed-session"}]
        replies = [{"status": 200, "content_type": "text/event-stream",
                    "body": b"data: " + json_bytes(chunk) + b"\n\n",
                    "chunked": True, "hold_open": True}, buffered_reply(created=42)]
        for binary in (ORACLE, MODEX):
            with self.subTest(case="committed", binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns, replies, idle_timeout_ms=100, lookahead_timeout_ms=500,
                )
                self.assertEqual([row["status"] for row in responses], [200, 503])
                self.assertEqual(len(posts), 1)

    def test_bound_continuation_ownership_matches_release(self):
        turns = [{"model": "deepseek-chat", "input": "first synthetic turn"},
                 {"model": "deepseek-chat", "input": "second synthetic turn", "use_previous": True}]
        replies = [buffered_reply(0, created=42), buffered_reply(1, created=43)]
        baseline_posts, baseline = observe_turns(ORACLE, turns, replies)
        modex_posts, modex = observe_turns(MODEX, turns, replies)
        self.assertEqual([row["status"] for row in baseline], [200, 503])
        self.assertEqual(len(baseline_posts), 1)
        self.assertEqual(json.loads(bytes.fromhex(baseline[1]["body"])), {
            "error": {"code": "bound_continuation_unavailable",
                      "message": "bound continuation provider is unavailable"},
        })
        self.assertEqual([row["status"] for row in modex], [200, 503])
        self.assertEqual(len(modex_posts), 1)
        self.assertEqual(json.loads(bytes.fromhex(modex[1]["body"])), {
            "error": {"code": "bound_continuation_unavailable",
                      "message": "bound continuation provider is unavailable"},
        })

    def test_streamed_history_prefetch_gap_and_credential_boundary(self):
        first = {
            "model": "deepseek-chat", "created": 42,
            "choices": [{"index": 0, "delta": {"content": "synthetic answer"}, "finish_reason": None}],
        }
        last = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        for name in ("prefix_id", "fallback_id", "late_id", "session", "different_client", "multiple_keys"):
            with self.subTest(case=name):
                initial = dict(first)
                if name != "fallback_id":
                    initial["id"] = "synthetic-streamed-id"
                final = dict(last)
                if name == "late_id":
                    final["id"] = "synthetic-streamed-id"
                first_frame = b"data: " + json_bytes(initial) + b"\n\n"
                wire = first_frame + b"data: " + json_bytes(final) + b"\n\ndata: [DONE]\n\n"
                reply = {"status": 200, "content_type": "text/event-stream", "body": wire}
                if name == "late_id":
                    reply.update({"chunked": True, "chunk_size": len(first_frame), "delay": 0.2})
                first_turn = {"model": "deepseek-chat", "input": "synthetic first", "stream": True}
                followup = {"model": "deepseek-chat", "input": "synthetic followup"}
                if name == "fallback_id":
                    followup["use_previous"] = True
                else:
                    followup["previous_response_id"] = "synthetic-streamed-id"
                if name == "session":
                    first_turn["session_id"] = followup["session_id"] = "synthetic-session"
                if name == "different_client":
                    followup["_headers"] = {"Authorization": "Bearer synthetic-other-client"}
                keys = "synthetic-key-a,synthetic-key-b" if name == "multiple_keys" else None
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    with self.subTest(binary=str(binary)):
                        posts, responses = observe_turns(binary, [first_turn, followup], [reply, buffered_reply(2)], api_keys=keys)
                        blocked = name in ("late_id", "session") or binary == MODEX
                        followup_status = 401 if name == "different_client" and binary == MODEX else 503 if blocked else 200
                        self.assertEqual([row["status"] for row in responses], [200, followup_status])
                        self.assertEqual(len(posts), 1 if blocked else 2)
                        if not blocked:
                            messages = json.loads(posts[1]["body"])["messages"]
                            self.assertEqual([item["content"] for item in messages],
                                             ["synthetic first", "synthetic answer", "synthetic followup"])
                        if name == "multiple_keys":
                            self.assertEqual([post["headers"]["authorization"] for post in posts],
                                             ["Bearer synthetic-key-a"] if blocked else
                                             ["Bearer synthetic-key-a", "Bearer synthetic-key-b"])

    def test_native_streamed_history_prefetch_gap(self):
        events = [
            {"type": "message_start", "message": {"id": "synthetic-native", "model": "deepseek-chat", "usage": {"input_tokens": 1}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "synthetic native answer"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
            {"type": "message_stop"},
        ]
        reply = {"status": 200, "content_type": "text/event-stream",
                 "body": b"".join(b"data: " + json_bytes(event) + b"\n\n" for event in events)}
        turns = [{"model": "deepseek-chat", "input": "synthetic first", "stream": True,
                  "tools": [{"type": "web_search_preview"}]},
                 {"model": "deepseek-chat", "input": "synthetic followup", "use_previous": True}]
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(binary, turns, [reply, buffered_reply(2)],
                                                 shared_config='[deepseek]\nweb_search_mode = "anthropic"\n')
                blocked = binary == MODEX
                self.assertEqual([row["status"] for row in responses], [200, 503 if blocked else 200])
                self.assertEqual(len(posts), 1 if blocked else 2)
                if not blocked:
                    messages = json.loads(posts[1]["body"])["messages"]
                    self.assertEqual([item["content"] for item in messages],
                                     ["synthetic first", "synthetic native answer", "synthetic followup"])

    def test_malformed_quota_reset_is_not_projected(self):
        reply = buffered_reply(created=42)
        reply["response_headers"] = [
            ("Content-Type", "application/json"),
            ("x-ratelimit-limit-requests", "100"),
            ("x-ratelimit-remaining-requests", "40"),
            ("x-ratelimit-reset-requests", "1.2.3s"),
        ]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [{"model": "deepseek-chat", "input": "synthetic quota reset"}], [reply],
                )
                self.assertEqual(len(upstream), 1)
                self.assertEqual(responses[0]["status"], 200)
                headers = {key.lower(): value for key, value in responses[0]["headers"].items()}
                self.assertEqual(headers.get("x-deepseek-requests-primary-used-percent"), "60")
                self.assertNotIn("x-deepseek-requests-primary-reset-at", headers)

    def test_oversized_buffered_provider_error_boundary_matches_release(self):
        # 2xx and 3xx buffered responses fail after provider response handoff;
        # >=400 bodies fail in the upstream request path instead.
        oversized = b"x" * (4 * 1024 * 1024 + 1)
        for route in ("chat/completions", "responses"):
            for status in (200, 302, 399, 400):
                for binary in (ORACLE, MODEX):
                    with self.subTest(route=route, status=status, binary=str(binary)):
                        upstream, responses = observe_turns(
                            binary,
                            [{"model": "deepseek-chat", "messages": [],
                              "_path": "/v1/" + route}],
                            [{"status": status, "content_type": "application/json",
                              "body": oversized}],
                        )
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(len(responses), 1)
                        self.assertEqual(responses[0]["status"], 502)
                        expected = (b"upstream request failed" if status >= 400 else
                                    b"provider response could not be processed")
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), expected)
                        self.assertEqual(upstream[0]["headers"]["authorization"],
                                         "Bearer " + SYNTHETIC_API_KEY)

    def test_oversized_chunked_buffered_provider_error_matches_release(self):
        # Chunked bodies cross the same boundary incrementally, not only via
        # a declared Content-Length check in the response head.
        oversized = b"x" * (4 * 1024 * 1024 + 1)
        for route in ("chat/completions", "responses"):
            for status in (200, 302, 400):
                for binary in (ORACLE, MODEX):
                    with self.subTest(route=route, status=status, binary=str(binary)):
                        upstream, responses = observe_turns(
                            binary,
                            [{"model": "deepseek-chat", "messages": [],
                              "_path": "/v1/" + route}],
                            [{"status": status, "content_type": "application/json",
                              "body": oversized, "chunked": True, "chunk_size": 713}],
                        )
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(responses[0]["status"], 502)
                        expected = (b"upstream request failed" if status >= 400 else
                                    b"provider response could not be processed")
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), expected)

    def test_oversized_redirect_sse_stays_streaming(self):
        oversized = b"x" * (4 * 1024 * 1024 + 1)
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    [{"model": "deepseek-chat", "messages": [],
                      "_path": "/v1/chat/completions"}],
                    [{"status": 302, "content_type": "text/event-stream",
                      "body": oversized}],
                )
                self.assertEqual(len(upstream), 1)
                self.assertEqual(responses[0]["status"], 302)
                self.assertEqual(bytes.fromhex(responses[0]["body"]), oversized)
                headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
                self.assertNotIn("content-length", headers)
                self.assertEqual(headers.get("transfer-encoding"), "chunked")

    def test_bodyless_passthrough_ignores_representation_length(self):
        cases = [("application/json", {"declared_length": 5 * 1024 * 1024 + 1}),
                 ("text/event-stream", {"declared_length": 5 * 1024 * 1024 + 1}),
                 ("application/json", {"chunked": True, "hold_open": True})]
        for content_type, framing in cases:
            for route in ("responses", "chat/completions"):
                for binary in (ORACLE, MODEX):
                    with self.subTest(framing=framing, route=route, binary=str(binary)):
                        upstream, responses = observe_turns(binary, [{"model": "deepseek-chat",
                            "input": "synthetic bodyless response", "messages": [],
                            "_path": "/v1/" + route + "?synthetic=%2B"}], [{"status": 304,
                            "content_type": content_type, "body": b"", **framing}])
                        self.assertEqual([row["status"] for row in responses], [304])
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), b"")
                        headers = {key.lower(): value for key, value in responses[0]["headers"].items()}
                        self.assertEqual(headers.get("content-length"),
                                         None if content_type == "text/event-stream" else "0")
                        self.assertEqual(headers.get("transfer-encoding"),
                                         "chunked" if content_type == "text/event-stream" else None)
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(upstream[0]["path"], "/v1/chat/completions" +
                                         ("?synthetic=%2B" if route == "chat/completions" else ""))
                        self.assertEqual(upstream[0]["headers"]["authorization"],
                                         "Bearer " + SYNTHETIC_API_KEY)

    def test_bodyless_sse_chunked_headers_match_release(self):
        # Frozen 0.439.2 omits a body and Content-Length while retaining TE.
        for status in (204, 304):
            # A 204 Responses message takes the separate response.failed path.
            routes = ("chat/completions",) if status == 204 else ("responses", "chat/completions")
            for route in routes:
                for framing in ({"declared_length": 5 * 1024 * 1024 + 1},
                                {"chunked": True, "hold_open": True}):
                    for binary in (ORACLE, MODEX):
                        with self.subTest(status=status, route=route, framing=framing,
                                          binary=str(binary)):
                            upstream, responses = observe_turns(
                                binary,
                                [{"model": "deepseek-chat", "input": "synthetic empty SSE",
                                  "_path": "/v1/" + route}],
                                [{"status": status, "content_type": "text/event-stream",
                                  "body": b"", **framing}],
                            )
                            self.assertEqual(len(upstream), 1)
                            self.assertEqual(len(responses), 1)
                            self.assertEqual(responses[0]["status"], status)
                            self.assertEqual(responses[0]["body"], "")
                            headers = {name.lower(): value
                                       for name, value in responses[0]["headers"].items()}
                            self.assertNotIn("content-length", headers)
                            self.assertEqual(headers.get("transfer-encoding"), "chunked")
                            self.assertEqual(upstream[0]["headers"]["authorization"],
                                             "Bearer " + SYNTHETIC_API_KEY)

    def test_upstream_dot_segments_match_release(self):
        cases = [('/v1/./keep', '/v1/keep/chat/completions'),
                 ('/v1/%2e/keep', '/v1/keep/chat/completions'),
                 ('/v1/%2E/keep', '/v1/keep/chat/completions'),
                 ('/v1/.', '/v1/chat/completions'),
                 ('/v1/%2E/', '/v1/chat/completions'),
                 ('/v1/left/../right', '/v1/right/chat/completions'),
                 ('/v1/left/.%2e/right', '/v1/right/chat/completions'),
                 ('/v1/left/%2E./right', '/v1/right/chat/completions'),
                 ('/v1/left/%2e%2E/right', '/v1/right/chat/completions'),
                 ('/v1/..', '/chat/completions'),
                 ('/v1/%2E%2e', '/chat/completions'),
                 ('/../../other', '/other/chat/completions'),
                 ('/v1//../other', '/v1/other/chat/completions'),
                 ('/v1/left/..//right', '/v1//right/chat/completions'),
                 ('/v1\\..\\other', '/other/chat/completions'),
                 ('/v1/left\\.%2E\\right', '/v1/right/chat/completions'),
                 ('/v1/left\\..\\\\right', '/v1//right/chat/completions'),
                 ('/v1/./trail\\', '/v1/trail//chat/completions'),
                 ('/v1/%252e/%252E%252e', '/v1/%252e/%252E%252e/chat/completions'),
                 ('/v1/%2e%2Fkeep/%5C', '/v1/%2e%2Fkeep/%5C/chat/completions'),
                 ('/v1/é/{東京}/..', '/v1/%C3%A9/chat/completions'),
                 ('/v1/é/../{東京}', '/v1/%7B%E6%9D%B1%E4%BA%AC%7D/chat/completions'),
                 ('/v1/part..part/.../.hidden', '/v1/part..part/.../.hidden/chat/completions')]
        query = "?keep=%2e%2E&encoded=%2F%5C"
        for path, target in cases:
            turns = [{"model": "deepseek-chat", "input": "synthetic dot normalization"},
                     {"model": "deepseek-chat", "messages": [],
                      "_path": "/v1/chat/completions" + query}]
            replies = [buffered_reply(created=42), {"status": 201,
                       "content_type": "application/json", "body": b"null"}]
            for binary in (ORACLE, MODEX):
                with self.subTest(path=path, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, replies, base_path=path)
                    self.assertEqual([row["status"] for row in responses], [200, 201])
                    self.assertEqual([row["path"] for row in upstream], [target, target + query])
                    for record in upstream:
                        self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_upstream_ascii_path_encoding_matches_release(self):
        paths = ['/v1/"<>`{}', '/v1/{}^|[]', '/v1/%22%3C%3E%60%7B%7D',
                 '/v1/é{"東京"}/', '/v1/a!$&\'()+,;=:_~-']
        expected = ['/v1/%22%3C%3E%60%7B%7D/chat/completions',
                    '/v1/%7B%7D^|[]/chat/completions',
                    '/v1/%22%3C%3E%60%7B%7D/chat/completions',
                    '/v1/%C3%A9%7B%22%E6%9D%B1%E4%BA%AC%22%7D/chat/completions',
                    '/v1/a!$&\'()+,;=:_~-/chat/completions']
        for path, target in zip(paths, expected):
            turns = [{"model": "deepseek-chat", "input": "synthetic path encoding"},
                     {"model": "deepseek-chat", "messages": [],
                      "_path": "/v1/chat/completions?synthetic=path%22&keep=%7B"}]
            reply = {"status": 201, "content_type": "application/json", "body": b"null"}
            for binary in (ORACLE, MODEX):
                with self.subTest(path=path, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, [buffered_reply(created=42), reply],
                                                         base_path=path)
                    self.assertEqual([row["status"] for row in responses], [200, 201])
                    self.assertEqual([row["path"] for row in upstream],
                                     [target, target + "?synthetic=path%22&keep=%7B"])
                    for record in upstream:
                        self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_upstream_backslash_separators_match_release(self):
        cases = [("/v1/left\\right", "/v1/left/right/chat/completions"),
                 ("/v1/left\\\\right", "/v1/left//right/chat/completions"),
                 ("/v1/trailing\\", "/v1/trailing//chat/completions"),
                 ("/v1/trailing\\/", "/v1/trailing//chat/completions"),
                 ("/v1/%5Cescaped", "/v1/%5Cescaped/chat/completions"),
                 ("/v1/é\\{東京}", "/v1/%C3%A9/%7B%E6%9D%B1%E4%BA%AC%7D/chat/completions")]
        for path, target in cases:
            turns = [{"model": "deepseek-chat", "input": "synthetic separator"},
                     {"model": "deepseek-chat", "messages": [],
                      "_path": "/v1/chat/completions?synthetic=%5C&keep=one"}]
            replies = [buffered_reply(created=42), {"status": 201,
                       "content_type": "application/json", "body": b"null"}]
            for binary in (ORACLE, MODEX):
                with self.subTest(path=path, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, replies, base_path=path)
                    self.assertEqual([row["status"] for row in responses], [200, 201])
                    self.assertEqual([row["path"] for row in upstream],
                                     [target, target + "?synthetic=%5C&keep=one"])
                    for record in upstream:
                        self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_annotation_accounting_cap_is_not_release_boundary(self):
        count = 100_000
        frame = b'data: ' + json_bytes({"choices": [{"delta": {"annotations": [None] * count}}]}) + b"\n\n"
        body = frame * 5 + b"data: [DONE]\n\n"
        self.assertLess(len(body), 4 * 1024 * 1024)
        self.assertGreater(count * 5 * (len("null") + 32), 16 * 1024 * 1024)
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, [{"model": "deepseek-chat",
                    "input": "synthetic annotation accounting", "stream": True}], [{"status": 200,
                    "content_type": "text/event-stream", "body": body, "chunked": True,
                    "chunk_size": 65536}])
                self.assertEqual(len(upstream), 1)
                self.assertEqual([row["status"] for row in responses], [200])
                payload = bytes.fromhex(responses[0]["body"])
                events = [json.loads(line[6:]) for line in payload.splitlines() if line.startswith(b"data: ")]
                self.assertEqual([event["type"] for event in events], ["response.created", "response.completed"])
                retained = events[-1]["response"]["metadata"]["deepseek"]["annotations"]
                self.assertEqual(len(retained), count * 5)
                self.assertTrue(all(item is None for item in retained))

    def test_invalid_continuation_identities_fail_before_provider_side_effects(self):
        invalid = ["a\0b", "a\x1fb", "a\x7fb", "a\x80b", "a\x9fb", "x" * 1025, "é" * 513]
        variants = [{"previous_response_id": value} for value in invalid]
        variants += [{"session_id": "a\x80b"}, {"client_metadata": {"session_id": "x" * 1025}},
                     {"_headers": {"session_id": "x" * 1025}},
                     {"_headers": {"x-codex-turn-state": "x" * 1025}},
                     {"_headers": {"x-codex-turn-metadata": json.dumps({"session_id": "a\0b"})}}]
        turns = [{"model": "deepseek-chat", "input": "synthetic invalid identity", **value}
                 for value in variants]
        error = {"error": {"code": "bound_continuation_unavailable",
                           "message": "bound continuation provider is unavailable"}}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [buffered_reply()] * len(turns))
                self.assertEqual(len(responses), len(turns))
                self.assertEqual(upstream, [])
                for response in responses:
                    self.assertEqual(response["status"], 503)
                    self.assertEqual(json.loads(bytes.fromhex(response["body"])), error)
                    headers = {name.lower(): value for name, value in response["headers"].items()}
                    self.assertEqual(headers["cache-control"], "no-store")
                    self.assertEqual(headers["x-content-type-options"], "nosniff")

    def test_super_tool_history_uses_local_file_access_context(self):
        call = {"id": "synthetic-scope-call", "type": "function",
                "function": {"name": "lookup", "arguments": "{}"}}
        message = {"role": "assistant", "content": "", "tool_calls": [call]}
        chunk = {"id": "synthetic-scope-chat", "created": 42, "model": "deepseek-chat",
                 "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, **call}]}}]}
        for streaming in (False, True):
            first = {"status": 200, "content_type": "application/json", "body": json_bytes({
                "id": "synthetic-scope-chat", "created": 42, "model": "deepseek-chat",
                "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
            })}
            if streaming:
                first.update(content_type="text/event-stream", body=(
                    b"data: " + json_bytes(chunk) + b'\n\ndata: {"choices":[{"delta":{},'
                    b'"finish_reason":"tool_calls"}]}\n\ndata: [DONE]\n\n'
                ))
            turns = [
                {"model": "deepseek-chat", "input": "synthetic history", "stream": streaming,
                 "session_id": "synthetic-body-a", "_headers": {
                     "session_id": "synthetic-header-a", "x-codex-turn-state": "synthetic-turn-a",
                     "x-prodex-internal-conversation-namespace": "synthetic-namespace-a"}},
                {"model": "deepseek-chat", "input": [{"type": "function_call_output",
                    "call_id": call["id"], "output": "synthetic result"}],
                 "safety_identifier": "synthetic-history-path",
                 "session_id": "synthetic-body-b", "_headers": {
                     "x-codex-turn-metadata": '{"session_id":"synthetic-metadata-b"}',
                     "x-codex-turn-state": "synthetic-turn-b",
                     "x-prodex-internal-conversation-namespace": "synthetic-namespace-b"}},
            ]
            observed = []
            for binary in (ORACLE, MODEX):
                with self.subTest(streaming=streaming, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, [first, buffered_reply(created=42)])
                    self.assertEqual([record["status"] for record in responses], [200, 200])
                    self.assertEqual(len(upstream), 2, "each accepted turn must send exactly one POST")
                    messages = json.loads(upstream[1]["body"])["messages"]
                    if binary == ORACLE:
                        self.assertEqual([item["role"] for item in messages], ["user", "assistant", "tool"])
                        self.assertEqual(messages[-1], {"role": "tool", "tool_call_id": call["id"],
                                                        "content": "synthetic result"})
                        self.assertEqual(messages[-2]["tool_calls"], [call])
                    else:
                        self.assertNotIn("synthetic history", json.dumps(messages))
                    self.assertEqual(upstream[1]["headers"]["x-codex-turn-state"], "synthetic-turn-b")
                    for record in upstream:
                        self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                        self.assertFalse(any(name.startswith("x-prodex-internal-") for name in record["headers"]))
                    observed.append([json.loads(record["body"]) for record in upstream])
            if len(observed) == 2:
                self.assertNotEqual(*observed)

    def test_equal_comma_list_upstream_framing_matches_release(self):
        for length, expected in (("4,4", 201), ("4, \t4", 201), ("4,5", 502), ("4,", 502)):
            reply = {"status": 201, "content_type": "application/json", "body": b"null",
                     "response_headers": [("Content-Type", "application/json"), ("Content-Length", length)]}
            turn = {"_path": "/v1/chat/completions", "model": "deepseek-chat", "messages": []}
            for binary in (ORACLE, MODEX):
                with self.subTest(length=length, binary=str(binary)):
                    upstream, responses = observe_turns(binary, [turn], [reply])
                    self.assertEqual([record["status"] for record in responses], [expected])
                    self.assertEqual(len(upstream), 1, "malformed framing must not replay a POST")
                    if expected == 201:
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), b"null")

    def test_call_id_field_priority_matches_release(self):
        variants = [{"call_id": None, "tool_call_id": "synthetic-alias"},
                    {"call_id": 7, "tool_call_id": "synthetic-alias"},
                    {"tool_call_id": None, "id": "synthetic-alias"},
                    {"call_id": "synthetic-primary", "tool_call_id": "synthetic-alias"},
                    {"id": "synthetic-only"}]
        turns = [{"model": "deepseek-chat", "input": [
            {"type": "function_call", "name": "lookup", **fields},
            {"type": "function_call_output", "output": "synthetic result", **fields},
        ]} for fields in variants]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, [buffered_reply(index, created=42)
                                                               for index in range(len(turns))])
            self.assertEqual([record["status"] for record in responses], [200] * len(turns))
            self.assertEqual(len(upstream), len(turns))
            observed.append([json.loads(record["body"]) for record in upstream])
        self.assertEqual(*observed)
        self.assertEqual([body["messages"][0]["tool_calls"][0]["id"] for body in observed[0]],
                         ["call_1", "call_1", "call_1", "synthetic-primary", "synthetic-only"])

    def test_malformed_response_format_rejects_before_provider_dispatch(self):
        variants = [{"response_format": value} for value in ({}, {"type": None}, {"type": 7},
                    {"type": False}, {"type": []}, {"type": {}}, {"type": "text"},
                    {"type": ""}, None, [], "text")]
        variants += [{"text": {"format": {"type": None}}},
                     {"response_format": {}, "text": {"format": {"type": "json_object"}}}]
        turns = [{"model": "deepseek-chat", "input": "synthetic format", **value} for value in variants]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, [buffered_reply(index, created=42)
                                                               for index in range(len(turns))])
            observed.append(([record["status"] for record in responses],
                             [json.loads(record["body"]) for record in upstream]))
        self.assertEqual(*observed)
        self.assertEqual(observed[0][0], [502] * 6 + [200] + [502] * 6)
        self.assertEqual(len(observed[0][1]), 1, "only the valid text format may reach the provider")
        self.assertNotIn("response_format", observed[0][1][0])

    def test_usage_decodes_escaped_keys_before_mapping_on_both_paths(self):
        usages = [
            r'{"prompt\u005ftokens":11,"completion_tokens":7}',
            r'{"prompt_tokens":1,"prompt\u005ftokens":2,"completion_tokens":3}',
            r'{"prompt\u005ftokens":2,"prompt_tokens":1,"completion_tokens":3}',
            r'{"prompt_tokens":5,"completion\u005ftokens_details":{"reasoning\u005ftokens":4}}',
            r'{"prompt_cache_hit\u005ftokens":0,"prompt_cache_miss_tokens":2,"total_tokens":0}',
            r'{"prompt_tokens":18446744073709551615,"completion_tokens":1}',
            r'{"prompt_tokens":18446744073709551616,"completion_tokens":-0,"total_tokens":2.0}',
            r'{"noise":[{"prompt_tokens":99,"text":"escaped \\\" brace }"}],"prompt_tokens":6}',
        ]
        for streaming in (False, True):
            turns = [{"model": "deepseek-chat", "input": "synthetic usage", "stream": streaming}
                     for _ in usages]
            replies = []
            for usage in usages:
                body = (b'{"id":"synthetic-usage","created":42,"model":"deepseek-chat",'
                        b'"choices":[],"usage":' + usage.encode() + b"}")
                replies.append({"status": 200,
                    "content_type": "text/event-stream" if streaming else "application/json",
                    "body": b"data: " + body + b"\n\ndata: [DONE]\n\n" if streaming else body})
            observed = []
            for binary in (ORACLE, MODEX):
                with self.subTest(streaming=streaming, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, replies)
                    self.assertEqual(len(upstream), len(turns))
                    mapped = []
                    for response in responses:
                        self.assertEqual(response["status"], 200)
                        body = bytes.fromhex(response["body"])
                        if streaming:
                            data = [json.loads(line[6:]) for line in body.splitlines()
                                    if line.startswith(b"data: ")]
                            value = data[-1]["response"]
                        else:
                            value = json.loads(body)
                        mapped.append(value["usage"])
                    self.assertEqual([item["input_tokens"] for item in mapped],
                                     [11, 2, 1, 5, 0, 18446744073709551615, 0, 6])
                    self.assertEqual(mapped[3]["output_tokens_details"], {"reasoning_tokens": 4})
                    observed.append(mapped)
            if len(observed) == 2:
                self.assertEqual(*observed)

    def test_reader_preserves_events_before_provider_error_in_one_frame(self):
        reply = {"status": 200, "content_type": "text/event-stream", "body": (
            b'data: {"id":"synthetic-reader","created":42,"choices":[{"delta":{"content":"kept"}}]}\n'
            b'data: {"error":{"message":"synthetic failure"}}\n\ndata: [DONE]\n\n'
        )}
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, [{"model": "deepseek-chat", "input": "synthetic",
                                                        "stream": True}], [reply])
            self.assertEqual(len(upstream), 1)
            self.assertEqual([record["status"] for record in responses], [200])
            body = bytes.fromhex(responses[0]["body"])
            names = [line[7:] for line in body.splitlines() if line.startswith(b"event: ")]
            self.assertEqual(names, [b"response.created", b"response.output_item.added",
                                     b"response.output_text.delta", b"response.failed"])
            self.assertIn(b'"delta":"kept"', body)
            self.assertIn(b"synthetic failure", body)
            data = [json.loads(line[6:]) for line in body.splitlines() if line.startswith(b"data: ")]
            observed.append((data[2]["delta"], data[3]["response"]["error"]))
        self.assertEqual(*observed)

    def test_buffered_passthrough_metadata_matches_release(self):
        values = ["synthetic-ascii", "synthetic\tmetadata", "synthetic-\x80",
                  "synthetic-\xff", "synthetic-\xc3\xa9"]
        payload = b"\x00synthetic metadata body\xff"
        for route, status in (("/v1/chat/completions?synthetic=metadata", 201), ("/v1/responses", 503)):
            turns = [{"model": "deepseek-chat", "_path": route,
                      **({"input": "synthetic"} if route == "/v1/responses" else {"messages": []}),
                      "_headers": {"x-codex-turn-state": f"synthetic-client-turn-{index}",
                          "x-codex-turn-metadata": json.dumps({"session_id": f"synthetic-metadata-{index}"}),
                          "x-prodex-internal-conversation-namespace": f"synthetic-namespace-{index}"}}
                     for index in range(len(values))]
            replies = [{"status": status, "content_type": "application/x-synthetic", "body": payload,
                        "response_headers": [("Content-Type", "application/x-synthetic"),
                            ("x-codex-turn-state", value), ("x-request-id", "synthetic-request"),
                            ("Connection", "X-Synthetic-Hop"), ("X-Synthetic-Hop", "strip-me")]}
                       for value in values]
            for binary in (ORACLE, MODEX):
                with self.subTest(route=route, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, replies)
                    self.assertEqual(len(upstream), len(turns), "metadata handling must never replay a POST")
                    self.assertEqual([row["status"] for row in responses], [status] * len(turns))
                    for index, response in enumerate(responses):
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertEqual(headers.get("x-codex-turn-state"), values[index] if index < 2 else None)
                        self.assertEqual(headers["x-request-id"], "synthetic-request")
                        self.assertNotIn("x-synthetic-hop", headers)
                        self.assertEqual(bytes.fromhex(response["body"]), payload)
                        sent = upstream[index]["headers"]
                        self.assertEqual(sent["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                        self.assertEqual(sent["x-codex-turn-state"], f"synthetic-client-turn-{index}")
                        self.assertFalse(any(name.startswith("x-prodex-internal-") for name in sent))

    def test_blank_session_headers_fall_through_aliases_before_metadata(self):
        invalid = "x" * 1025
        cases = [({"session_id": " ", "x-session-id": invalid}, 503),
                 ({"session_id": " ", "session-id": "synthetic-valid-second", "x-session-id": invalid}, 200),
                 ({"session-id": "\t", "x-session-id": invalid}, 503),
                 ({"session_id": "synthetic-valid-first", "session-id": invalid}, 200),
                 ({"session_id": " ", "session-id": "\t", "x-session-id": " "}, 200),
                 ({"session_id": " ", "x-session-id": "synthetic-valid-last",
                   "x-codex-turn-metadata": json.dumps({"session_id": invalid})}, 200)]
        turns = [{"model": "deepseek-chat", "input": "synthetic alias priority",
                  "session_id": "synthetic-body", "_headers": headers} for headers, _ in cases]
        expected = [status for _, status in cases]
        error = {"error": {"code": "bound_continuation_unavailable",
                           "message": "bound continuation provider is unavailable"}}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [buffered_reply(index, created=42)
                                                                   for index in range(len(turns))])
                self.assertEqual([row["status"] for row in responses], expected)
                self.assertEqual(len(upstream), expected.count(200), "rejected identities must send zero POSTs")
                for response in responses:
                    if response["status"] == 503:
                        self.assertEqual(json.loads(bytes.fromhex(response["body"])), error)
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertEqual(headers["cache-control"], "no-store")
                        self.assertEqual(headers["x-content-type-options"], "nosniff")
                for record in upstream:
                    self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_valid_identity_boundaries_and_header_precedence_match_release(self):
        variants = [{"previous_response_id": "é" * 512}, {"session_id": "s" * 1024},
                    {"previous_response_id": " \t \n "},
                    {"_headers": {"session_id": "valid-first", "x-session-id": "x" * 1025}},
                    {"_headers": {"x-codex-turn-state": "t" * 1024}}]
        turns = [{"model": "deepseek-chat", "input": "synthetic valid identity", **value}
                 for value in variants]
        replies = [buffered_reply(index, created=42) for index in range(len(turns))]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual([response["status"] for response in responses], [200] * len(turns))
            for record in upstream:
                self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                self.assertEqual(record["path"], "/v1/chat/completions")
            observed.append([json.loads(record["body"]) for record in upstream])
        self.assertEqual(*observed)

    def test_created_fallback_and_unsigned_values_match_release(self):
        fields = [{}, {"created": None}, {"created": -1}, {"created": False},
                  {"created": "42"}, {"created": 0}, {"created": 42}]
        turns = [{"model": "deepseek-chat", "input": "synthetic timestamp"} for _ in fields]
        replies = [buffered_reply(index, **value) for index, value in enumerate(fields)]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual(len(responses), len(turns))
            bodies = []
            for index, response in enumerate(responses):
                self.assertEqual(response["status"], 200)
                body = json.loads(bytes.fromhex(response["body"]))
                created = body.pop("created_at")
                if index < 5:
                    self.assertGreaterEqual(created, response["started"])
                    self.assertLessEqual(created, response["finished"])
                else:
                    self.assertEqual(created, fields[index]["created"])
                bodies.append(body)
            observed.append(bodies)
        self.assertEqual(*observed)

    def test_delayed_created_fallback_matches_release(self):
        reply = buffered_reply(ignored="x" * 80)
        reply.update(chunk_size=(len(reply["body"]) + 1) // 2, delay=1.2)
        turns = [{"model": "deepseek-chat", "input": "synthetic delayed timestamp"}]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [reply])
                self.assertEqual(len(upstream), 1)
                response = responses[0]
                created = json.loads(bytes.fromhex(response["body"]))["created_at"]
                self.assertGreater(created, response["started"])
                self.assertLessEqual(created, response["finished"])

    def test_unicode_upstream_base_paths_match_release_without_double_encoding(self):
        cases = [("/v1/é/東京🧭", "/v1/%C3%A9/%E6%9D%B1%E4%BA%AC%F0%9F%A7%AD"),
                 ("/v1/%C3%A9/%2f", "/v1/%C3%A9/%2f"),
                 ("/v1/e\u0301", "/v1/e%CC%81"),
                 ("/v1/%E6%9D%B1/🧭/", "/v1/%E6%9D%B1/%F0%9F%A7%AD")]
        for base_path, encoded in cases:
            for route in ("/v1/responses", "/v1/chat/completions?synthetic=1"):
                turns = [{"model": "deepseek-chat", "input": "synthetic unicode base path", "_path": route}]
                for binary in (ORACLE, MODEX):
                    with self.subTest(base_path=base_path, route=route, binary=str(binary)):
                        upstream, responses = observe_turns(binary, turns, [buffered_reply(created=42)],
                                                            base_path=base_path)
                        self.assertEqual([response["status"] for response in responses], [200])
                        self.assertEqual(len(upstream), 1)
                        query = "?synthetic=1" if "?" in route else ""
                        self.assertEqual(upstream[0]["path"], encoded + "/chat/completions" + query)
                        self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)


if __name__ == "__main__":
    unittest.main()
