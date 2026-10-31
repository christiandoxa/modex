"""Pin upstream pool ownership across loopback redirects in Prodex 0.166.2."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_super_launch as launch_support


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_API_KEY = "synthetic-provider-key"
TEST_VERSION = "0.166.2"
CODEX_PREFIX = launch_support.CODEX[:launch_support.CODEX.index("passthrough = scenario")]
POOL_CLIENT = CODEX_PREFIX + r'''
import http.client, socket
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = socket.create_connection((target.hostname, target.port), timeout=5)
connection.settimeout(5)
def send(path, close, marker):
    body = json.dumps({"model":"deepseek-chat","messages":[],"synthetic":marker},separators=(",", ":")).encode()
    headers = [f"Host: {target.hostname}:{target.port}", "Content-Type: application/json",
               "Authorization: " + authorization, f"Content-Length: {len(body)}"]
    if close:
        headers.append("Connection: close")
    request = (f"POST {path} HTTP/1.1\r\n" + "\r\n".join(headers) + "\r\n\r\n").encode() + body
    connection.sendall(request)
    response = http.client.HTTPResponse(connection)
    response.begin()
    payload = response.read()
    return {"status": response.status, "body": payload.hex()}
responses = [
    send("/v1/chat/completions?synthetic=redirect", False, "first"),
    send("/v1/chat/completions?synthetic=second", True, "second"),
]
connection.close()
save({"kind":"pool-redirect", "responses":responses})
print("synthetic-pool-redirect-complete")
raise SystemExit(0)
'''

ROTATE_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
body = json.dumps({"model":"deepseek-chat","messages":[]},separators=(",", ":")).encode()
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
connection.request("POST", "/v1/chat/completions", body,
                   {"Content-Type":"application/json", "Authorization":authorization,
                    "Connection":"close"})
response = connection.getresponse()
payload = response.read()
save({"kind":"pool-rotate", "response":{"status":response.status, "body":payload.hex()}})
connection.close()
print("synthetic-pool-rotate-complete")
raise SystemExit(0)
'''

CONCURRENT_CLIENT = CODEX_PREFIX + r'''
import http.client, threading
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
def request(marker):
    body = json.dumps({"model":"deepseek-chat","messages":[],"synthetic":marker},separators=(",", ":")).encode()
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
    connection.request("POST", "/v1/chat/completions?synthetic="+marker, body,
                       {"Content-Type":"application/json", "Authorization":authorization,
                        "Connection":"close"})
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return {"status":response.status, "body":payload.hex()}
warm = request("warm")
results = {}
barrier = threading.Barrier(3)
def concurrent(marker):
    barrier.wait()
    results[marker] = request(marker)
threads = [threading.Thread(target=concurrent, args=(marker,)) for marker in ("parallel-a", "parallel-b")]
for thread in threads: thread.start()
barrier.wait()
for thread in threads: thread.join(10)
if any(thread.is_alive() for thread in threads):
    raise RuntimeError("parallel downstream requests did not finish")
save({"kind":"pool-concurrent", "warm":warm, "parallel":results})
print("synthetic-pool-concurrent-complete")
raise SystemExit(0)
'''

STALE_IDLE_CLIENT = CODEX_PREFIX + r'''
import http.client, time
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
def send(path, close):
    body = json.dumps({"model":"deepseek-chat","messages":[]},separators=(",", ":")).encode()
    headers = {"Content-Type":"application/json", "Authorization":authorization}
    if close: headers["Connection"] = "close"
    connection.request("POST", path, body, headers)
    response = connection.getresponse()
    payload = response.read()
    return {"status":response.status, "body":payload.hex()}
responses = [send("/v1/chat/completions?synthetic=before-idle-close", False)]
time.sleep(0.5)
responses.append(send("/v1/chat/completions?synthetic=after-idle-close", True))
connection.close()
save({"kind":"pool-idle", "responses":responses})
print("synthetic-pool-idle-complete")
raise SystemExit(0)
'''

CANCEL_CLIENT = CODEX_PREFIX + r'''
import http.client, socket
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
body = json.dumps({"model":"deepseek-chat","messages":[],"stream":True},separators=(",", ":")).encode()
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
connection.request("POST", "/v1/chat/completions?synthetic=cancel", body,
                   {"Content-Type":"application/json", "Authorization":authorization})
first = connection.getresponse()
first_status = first.status
connection.close()
followup = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
body = json.dumps({"model":"deepseek-chat","messages":[]},separators=(",", ":")).encode()
followup.request("POST", "/v1/chat/completions?synthetic=after-cancel", body,
                 {"Content-Type":"application/json", "Authorization":authorization,
                  "Connection":"close"})
second = followup.getresponse()
second_body = second.read()
save({"kind":"pool-cancel", "statuses":[first_status, second.status], "body":second_body.hex()})
followup.close()
print("synthetic-pool-cancel-complete")
raise SystemExit(0)
'''

RESPONSES_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
def send(path, close, marker):
    body = json.dumps({"model":"deepseek-chat","input":"synthetic "+marker},separators=(",", ":")).encode()
    headers = {"Content-Type":"application/json", "Authorization":authorization}
    if close: headers["Connection"] = "close"
    connection.request("POST", path, body, headers)
    response = connection.getresponse()
    payload = response.read()
    return {"status":response.status, "body":payload.hex()}
responses = [
    send("/v1/responses?synthetic=first", False, "first"),
    send("/v1/responses?synthetic=second", True, "second"),
]
connection.close()
save({"kind":"pool-responses", "responses":responses})
print("synthetic-pool-responses-complete")
raise SystemExit(0)
'''

RESPONSES_ROTATE_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
body = json.dumps({"model":"deepseek-chat","input":"synthetic key retry"},separators=(",", ":")).encode()
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
connection.request("POST", "/v1/responses", body,
                   {"Content-Type":"application/json", "Authorization":authorization,
                    "Connection":"close"})
response = connection.getresponse()
payload = response.read()
save({"kind":"pool-responses-retry", "response":{"status":response.status, "body":payload.hex()}})
connection.close()
print("synthetic-pool-responses-retry-complete")
raise SystemExit(0)
'''

AUTH_SCHEME_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
def send(path, body_value, close):
    body = json.dumps(body_value,separators=(",", ":")).encode()
    headers = {"Content-Type":"application/json", "Authorization":authorization}
    if close: headers["Connection"] = "close"
    connection.request("POST", path, body, headers)
    response = connection.getresponse()
    payload = response.read()
    return {"status":response.status, "body":payload.hex()}
chat = {"model":"deepseek-chat", "messages":[]}
messages = {"model":"deepseek-chat", "messages":[{"role":"user", "content":"synthetic"}], "max_tokens":8}
responses = [
    send("/v1/chat/completions?synthetic=chat-one", chat, False),
    send("/v1/chat/completions?synthetic=chat-two", chat, False),
    send("/v1/messages", messages, False),
    send("/v1/messages", messages, True),
]
connection.close()
save({"kind":"pool-auth-scheme", "responses":responses})
print("synthetic-pool-auth-scheme-complete")
raise SystemExit(0)
'''

NATIVE_REDIRECT_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
def send(path, body_value, close):
    body = json.dumps(body_value,separators=(",", ":")).encode()
    headers = {"Content-Type":"application/json", "Authorization":authorization}
    if close: headers["Connection"] = "close"
    connection.request("POST", path, body, headers)
    response = connection.getresponse()
    payload = response.read()
    return {"status":response.status, "body":payload.hex()}
native = {"model":"deepseek-chat", "input":"synthetic native exchange",
          "tools":[{"type":"web_search_preview"}]}
messages = {"model":"deepseek-chat", "messages":[{"role":"user", "content":"synthetic direct"}],
            "max_tokens":8}
responses = [
    send("/v1/responses", native, False),
    send("/v1/messages", messages, True),
]
connection.close()
save({"kind":"pool-native-auth-scheme", "responses":responses})
print("synthetic-pool-native-auth-scheme-complete")
raise SystemExit(0)
'''

X_API_KEY_ROTATE_CLIENT = CODEX_PREFIX + r'''
import http.client
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=8)
body = json.dumps({"model":"deepseek-chat", "messages":[{"role":"user", "content":"synthetic"}],
                   "max_tokens":8},separators=(",", ":")).encode()
connection.request("POST", "/v1/messages", body,
                   {"Content-Type":"application/json", "Authorization":authorization,
                    "Connection":"close"})
response = connection.getresponse()
payload = response.read()
connection.close()
save({"kind":"pool-x-api-key-rotate", "response":{"status":response.status, "body":payload.hex()}})
print("synthetic-pool-x-api-key-rotate-complete")
raise SystemExit(0)
'''

JSON_REPLY = b'{"id":"synthetic-pool","model":"deepseek-chat","choices":[]}'
ANTHROPIC_REPLY = (
    b'{"id":"synthetic-message","type":"message","role":"assistant",'
    b'"model":"deepseek-chat","content":[{"type":"text","text":"synthetic reply"}],'
    b'"stop_reason":"end_turn","usage":{"input_tokens":2,"output_tokens":1}}'
)
DEEPSEEK_CHAT_REPLY = (
    b'{"id":"synthetic-chat","model":"deepseek-chat","choices":'
    b'[{"index":0,"message":{"role":"assistant","content":"synthetic reply"},'
    b'"finish_reason":"stop"}]}'
)


def _response(status, body, headers=()):
    fields = [f"HTTP/1.1 {status} Synthetic\r\n".encode()]
    fields.extend(name.encode("ascii") + b": " + value.encode("ascii") + b"\r\n" for name, value in headers)
    fields.extend((b"Content-Length: " + str(len(body)).encode() + b"\r\n", b"Connection: keep-alive\r\n\r\n", body))
    return b"".join(fields)


class RawPeer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.records = []
        self.accepts = []
        self.closed_ports = []
        self.release_after = 0
        self.hold_first = False
        self.close_first_after_delay = False
        self.barrier_timed_out = False
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        super().__init__(("127.0.0.1", 0), RawPeerHandler)

    def get_request(self):
        request, address = super().get_request()
        with self._lock:
            self.accepts.append(address[1])
        return request, address

    def take_reply(self):
        with self._lock:
            return self.replies.pop(0) if self.replies else _response(500, b"unexpected request")

    def wait_closed(self, port, timeout=3):
        with self._condition:
            return self._condition.wait_for(lambda: port in self.closed_ports, timeout)


class RawPeerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(8)
        reader = self.request.makefile("rb")
        try:
            while True:
                request_line = reader.readline()
                if not request_line:
                    return
                headers = {}
                while True:
                    line = reader.readline()
                    if line in (b"\r\n", b""):
                        break
                    name, value = line.split(b":", 1)
                    headers[name.strip().lower()] = value.strip()
                if line == b"":
                    return
                length = int(headers.get(b"content-length", b"0"))
                body = reader.read(length)
                if len(body) != length:
                    return
                method, path, _version = request_line.decode("ascii").strip().split(" ", 2)
                with self.server._condition:
                    self.server.records.append({
                        "method": method,
                        "path": path,
                        "headers": headers,
                        "body": body,
                        "client_port": self.client_address[1],
                    })
                    request_count = len(self.server.records)
                    self.server._condition.notify_all()
                if self.server.release_after and request_count > 1:
                    with self.server._condition:
                        if not self.server._condition.wait_for(
                            lambda: len(self.server.records) >= self.server.release_after,
                            timeout=4,
                        ):
                            self.server.barrier_timed_out = True
                reply = self.server.take_reply()
                close_after = False
                if isinstance(reply, tuple):
                    reply, close_after = reply
                self.request.sendall(reply)
                if self.server.hold_first and request_count == 1:
                    try:
                        if self.request.recv(1) == b"":
                            pass
                    except (OSError, TimeoutError):
                        pass
                    return
                if self.server.close_first_after_delay and request_count == 1:
                    time.sleep(0.2)
                    return
                if close_after:
                    return
                if headers.get(b"connection", b"").lower() == b"close":
                    return
        except (OSError, TimeoutError, ValueError):
            return
        finally:
            reader.close()
            with self.server._condition:
                self.server.closed_ports.append(self.client_address[1])
                self.server._condition.notify_all()


@contextmanager
def serving(server):
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _run(binary, upstream_port, *, client_script=POOL_CLIENT, client_kind="pool-redirect", api_keys=None):
    with tempfile.TemporaryDirectory(prefix="modex-upstream-pool-01662-") as directory:
        root = Path(directory)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(json.dumps({
            "source": "GitHub", "latest_version": TEST_VERSION,
            "checked_at": 4102444800,
        }, separators=(",", ":")))
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + client_script, encoding="utf-8")
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "TERM": "dumb", "NO_COLOR": "1",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        if api_keys is not None:
            environment["DEEPSEEK_API_KEYS"] = api_keys
        provider_args = [] if api_keys is not None else ["--api-key", SYNTHETIC_API_KEY]
        result = subprocess.run(
            [str(binary), "super", "--provider", "deepseek", *provider_args,
             "--base-url", f"http://127.0.0.1:{upstream_port}/v1", "--model", "deepseek-chat",
             "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
            cwd=root / "work", env=environment, capture_output=True, timeout=25,
        )
        marker = f"synthetic-{client_kind}-complete".encode()
        if result.returncode != 0 or marker not in result.stdout:
            records = capture.read_text(encoding="utf-8").splitlines() if capture.exists() else []
            raise AssertionError((result.returncode, result.stdout, result.stderr, records))
        records = [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()]
        clients = [record for record in records if record.get("kind") == client_kind]
        if len(clients) != 1:
            raise AssertionError(f"expected one pool redirect capture, got {len(clients)}")
        return clients[0]


class ProviderUpstreamPoolOwnership01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from manual_real_codex_01660_route_comparison import require_isolated_environment
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_canonical_loopback_alias_keeps_pool_on_original_endpoint(self):
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                port_holder = RawPeer()
                with serving(port_holder) as upstream:
                    upstream.replies = [
                        _response(302, b"synthetic redirect", (("Location", f"http://127.1:{upstream.server_address[1]}/v1/redirected?synthetic=alias"), ("Content-Type", "text/plain"))),
                        _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
                        _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
                    ]
                    responses = _run(binary, upstream.server_address[1])["responses"]
                    records = list(upstream.records)
                self.assertEqual([response["status"] for response in responses], [200, 200])
                self.assertEqual(len(records), 3)
                self.assertEqual([(row["method"], row["path"]) for row in records], [
                    ("POST", "/v1/chat/completions?synthetic=redirect"),
                    ("GET", "/v1/redirected?synthetic=alias"),
                    ("POST", "/v1/chat/completions?synthetic=second"),
                ])
                self.assertEqual(records[0]["headers"][b"host"], records[1]["headers"][b"host"])
                self.assertEqual(records[1]["headers"][b"host"], records[2]["headers"][b"host"])
                self.assertEqual(records[1]["client_port"], records[2]["client_port"])
                self.assertTrue(all(row["headers"].get(b"authorization") == b"Bearer " + SYNTHETIC_API_KEY.encode() for row in records))
                if binary == MODEX:
                    self.assertTrue(upstream.wait_closed(records[-1]["client_port"]),
                                    "runtime teardown must close the idle pooled socket")

    def test_cross_port_redirect_is_not_contacted_and_next_request_uses_original_pool_key(self):
        original = RawPeer()
        other = RawPeer([_response(200, b"wrong endpoint", (("Content-Type", "text/plain"),))])
        with serving(original), serving(other):
            original.replies = [
                _response(302, b"synthetic redirect", (("Location", f"http://127.0.0.1:{other.server_address[1]}/v1/should-not-be-contacted"), ("Content-Type", "text/plain"))),
                _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            ]
            responses = _run(MODEX, original.server_address[1])["responses"]
            original_records = list(original.records)
            other_accepts = list(other.accepts)
        self.assertEqual([response["status"] for response in responses], [302, 200])
        self.assertEqual([(row["method"], row["path"]) for row in original_records], [
            ("POST", "/v1/chat/completions?synthetic=redirect"),
            ("POST", "/v1/chat/completions?synthetic=second"),
        ])
        self.assertEqual(len(original_records), 2)
        self.assertEqual(original_records[0]["client_port"], original_records[1]["client_port"])
        self.assertEqual(other_accepts, [], "the cross-port redirect endpoint must not be contacted")
        self.assertTrue(original.wait_closed(original_records[-1]["client_port"]),
                        "runtime teardown must close the idle pooled socket")

    def test_401_rotation_does_not_reuse_connection_across_credentials(self):
        keys = "synthetic-pool-key-a,synthetic-pool-key-b"
        upstream = RawPeer([
            _response(401, b'{"error":{"code":"invalid_api_key"}}', (("Content-Type", "application/json"),)),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            responses = _run(
                MODEX, upstream.server_address[1], client_script=ROTATE_CLIENT,
                client_kind="pool-rotate", api_keys=keys,
            )
            records = list(upstream.records)
        self.assertEqual(responses["response"]["status"], 200)
        self.assertEqual(len(records), 2)
        self.assertEqual([row["headers"].get(b"authorization") for row in records], [
            b"Bearer synthetic-pool-key-a", b"Bearer synthetic-pool-key-b",
        ])
        self.assertNotEqual(records[0]["client_port"], records[1]["client_port"],
                            "a completed 401 connection must remain scoped to its credential")

    def test_same_credential_does_not_cross_bearer_and_x_api_key_pool_scopes(self):
        upstream = RawPeer([
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=AUTH_SCHEME_CLIENT,
                client_kind="pool-auth-scheme",
            )
            records = list(upstream.records)
        self.assertEqual([row["status"] for row in capture["responses"]], [200, 200, 200, 200])
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["client_port"], records[1]["client_port"],
                         "Bearer requests with the same key and endpoint should reuse")
        self.assertEqual(records[2]["client_port"], records[3]["client_port"],
                         "x-api-key requests with the same key and endpoint should reuse")
        self.assertNotEqual(records[1]["client_port"], records[2]["client_port"],
                            "the same credential must not reuse a socket across auth schemes")
        self.assertEqual([row["headers"].get(b"authorization") for row in records[:2]], [
            b"Bearer " + SYNTHETIC_API_KEY.encode(), b"Bearer " + SYNTHETIC_API_KEY.encode(),
        ])
        self.assertTrue(all(b"x-api-key" not in row["headers"] for row in records[:2]))
        self.assertEqual([row["headers"].get(b"x-api-key") for row in records[2:]], [
            SYNTHETIC_API_KEY.encode(), SYNTHETIC_API_KEY.encode(),
        ])
        self.assertTrue(all(b"authorization" not in row["headers"] for row in records[2:]))

    def test_native_exchange_redirect_returns_x_api_key_socket_to_messages_pool(self):
        upstream = RawPeer()
        upstream.replies = [
            _response(302, b"synthetic native redirect", (
                ("Location", f"http://127.1:{upstream.server_address[1]}/anthropic/v1/native-redirect"),
                ("Content-Type", "text/plain"),
            )),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
        ]
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=NATIVE_REDIRECT_CLIENT,
                client_kind="pool-native-auth-scheme",
            )
            records = list(upstream.records)
        self.assertEqual([row["status"] for row in capture["responses"]], [200, 200])
        self.assertEqual([(row["method"], row["path"]) for row in records], [
            ("POST", "/anthropic/v1/messages"),
            ("GET", "/anthropic/v1/native-redirect"),
            ("POST", "/anthropic/v1/messages"),
        ])
        self.assertEqual(len(records), 3)
        self.assertTrue(all(row["headers"].get(b"x-api-key") == SYNTHETIC_API_KEY.encode() for row in records))
        self.assertTrue(all(b"authorization" not in row["headers"] for row in records))
        self.assertTrue(all(row["headers"].get(b"anthropic-version") == b"2023-06-01" for row in records))
        self.assertEqual(records[1]["client_port"], records[2]["client_port"],
                         "the native exchange redirect response should return an x-api-key socket reusable by passthrough")

    def test_x_api_key_401_retry_returns_socket_to_its_credential_scope(self):
        key = "synthetic-x-api-key-same"
        keys = f"{key},{key}"
        upstream = RawPeer([
            _response(401, b'{"error":{"code":"invalid_api_key"}}', (("Content-Type", "application/json"),)),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=X_API_KEY_ROTATE_CLIENT,
                client_kind="pool-x-api-key-rotate", api_keys=keys,
            )
            records = list(upstream.records)
        self.assertEqual(capture["response"]["status"], 200)
        self.assertEqual(len(records), 2)
        self.assertEqual([row["headers"].get(b"x-api-key") for row in records], [
            key.encode(), key.encode(),
        ])
        self.assertTrue(all(b"authorization" not in row["headers"] for row in records))
        self.assertEqual(records[0]["client_port"], records[1]["client_port"],
                         "the completed 401 socket should return to its x-api-key and credential scope")

    def test_x_api_key_401_retry_opens_new_socket_for_rotated_credential(self):
        first_key = "synthetic-x-api-key-a"
        second_key = "synthetic-x-api-key-b"
        upstream = RawPeer([
            _response(401, b'{"error":{"code":"invalid_api_key"}}', (("Content-Type", "application/json"),)),
            _response(200, ANTHROPIC_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=X_API_KEY_ROTATE_CLIENT,
                client_kind="pool-x-api-key-rotate", api_keys=f"{first_key},{second_key}",
            )
            records = list(upstream.records)
        self.assertEqual(capture["response"]["status"], 200)
        self.assertEqual(len(records), 2)
        self.assertEqual([row["headers"].get(b"x-api-key") for row in records], [
            first_key.encode(), second_key.encode(),
        ])
        self.assertTrue(all(b"authorization" not in row["headers"] for row in records))
        self.assertNotEqual(records[0]["client_port"], records[1]["client_port"],
                            "a 401 connection must not cross into the rotated credential's scope")

    def test_buffered_responses_success_reuses_connection_across_requests(self):
        upstream = RawPeer([
            _response(200, DEEPSEEK_CHAT_REPLY, (("Content-Type", "application/json"),)),
            _response(200, DEEPSEEK_CHAT_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=RESPONSES_CLIENT,
                client_kind="pool-responses",
            )
            records = list(upstream.records)
        self.assertEqual([row["status"] for row in capture["responses"]], [200, 200])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["client_port"], records[1]["client_port"])
        self.assertEqual([row["headers"].get(b"authorization") for row in records], [
            b"Bearer " + SYNTHETIC_API_KEY.encode(), b"Bearer " + SYNTHETIC_API_KEY.encode(),
        ])

    def test_buffered_responses_final_error_is_drained_and_reusable(self):
        upstream = RawPeer([
            _response(400, b'{"error":{"type":"invalid_request","message":"synthetic final error"}}',
                      (("Content-Type", "application/json"),)),
            _response(200, DEEPSEEK_CHAT_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=RESPONSES_CLIENT,
                client_kind="pool-responses",
            )
            records = list(upstream.records)
        self.assertEqual([row["status"] for row in capture["responses"]], [400, 200])
        self.assertEqual(len(records), 2, "a final error response must not be replayed")
        self.assertEqual(records[0]["client_port"], records[1]["client_port"],
                         "fully consumed final errors can return their socket to the same key scope")

    def test_buffered_responses_401_retry_rotates_key_and_socket_scope(self):
        keys = "synthetic-responses-key-a,synthetic-responses-key-b"
        upstream = RawPeer([
            _response(401, b'{"error":{"code":"invalid_api_key"}}', (("Content-Type", "application/json"),)),
            _response(200, DEEPSEEK_CHAT_REPLY, (("Content-Type", "application/json"),)),
        ])
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=RESPONSES_ROTATE_CLIENT,
                client_kind="pool-responses-retry", api_keys=keys,
            )
            records = list(upstream.records)
        self.assertEqual(capture["response"]["status"], 200)
        self.assertEqual(len(records), 2)
        self.assertEqual([row["headers"].get(b"authorization") for row in records], [
            b"Bearer synthetic-responses-key-a", b"Bearer synthetic-responses-key-b",
        ])
        self.assertNotEqual(records[0]["client_port"], records[1]["client_port"],
                            "DeepSeekExchange retry must not cross credential pool scopes")

    def test_pool_checkout_does_not_serialize_network_io(self):
        upstream = RawPeer([
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
        ])
        upstream.release_after = 3
        with serving(upstream):
            captures = _run(
                MODEX, upstream.server_address[1], client_script=CONCURRENT_CLIENT,
                client_kind="pool-concurrent",
            )
            records = list(upstream.records)
            barrier_timed_out = upstream.barrier_timed_out
        self.assertEqual(captures["warm"]["status"], 200)
        self.assertEqual({row["status"] for row in captures["parallel"].values()}, {200})
        self.assertEqual(len(records), 3)
        self.assertEqual({row["path"] for row in records[1:]}, {
            "/v1/chat/completions?synthetic=parallel-a",
            "/v1/chat/completions?synthetic=parallel-b",
        })
        self.assertNotEqual(records[1]["client_port"], records[2]["client_port"],
                            "one request may check out the idle socket while the other opens a miss")
        self.assertFalse(barrier_timed_out, "concurrent upstream requests were serialized behind pool I/O")

    def test_stale_idle_peer_is_discarded_at_checkout(self):
        upstream = RawPeer([
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
        ])
        upstream.close_first_after_delay = True
        with serving(upstream):
            capture = _run(
                MODEX, upstream.server_address[1], client_script=STALE_IDLE_CLIENT,
                client_kind="pool-idle",
            )
            records = list(upstream.records)
        self.assertEqual([row["status"] for row in capture["responses"]], [200, 200])
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["client_port"], records[1]["client_port"],
                            "a peer-closed idle socket must be discarded on the next checkout")

    def test_close_delimited_response_is_not_pooled_and_truncated_chunked_is_not_replayed(self):
        cases = (
            (
                "close-delimited",
                (b"HTTP/1.1 200 Synthetic\r\nContent-Type: application/json\r\n"
                 b"Connection: close\r\n\r\n" + JSON_REPLY, True),
                [200, 200],
            ),
            (
                "truncated-chunked",
                (b"HTTP/1.1 200 Synthetic\r\nContent-Type: application/json\r\n"
                 b"Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
                 b"5\r\nshort\r\n", True),
                [502, 200],
            ),
        )
        for name, first_reply, expected_statuses in cases:
            with self.subTest(case=name):
                upstream = RawPeer([
                    first_reply,
                    _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
                ])
                with serving(upstream):
                    responses = _run(MODEX, upstream.server_address[1])["responses"]
                    records = list(upstream.records)
                self.assertEqual([response["status"] for response in responses], expected_statuses)
                self.assertEqual(len(records), 2, "the incomplete response must not trigger replay")
                self.assertNotEqual(records[0]["client_port"], records[1]["client_port"],
                                    "a non-reusable or truncated response must be discarded")

    def test_downstream_cancel_closes_stream_socket_without_pooling_it(self):
        sse_head = (
            b"HTTP/1.1 200 Synthetic\r\nContent-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
        )
        upstream = RawPeer([
            (sse_head, False),
            _response(200, JSON_REPLY, (("Content-Type", "application/json"),)),
        ])
        upstream.hold_first = True
        with serving(upstream):
            captures = _run(
                MODEX, upstream.server_address[1], client_script=CANCEL_CLIENT,
                client_kind="pool-cancel",
            )
            records = list(upstream.records)
        self.assertEqual(captures["statuses"], [200, 200])
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["client_port"], records[1]["client_port"])
        self.assertTrue(upstream.wait_closed(records[0]["client_port"]),
                        "downstream cancellation must release the upstream stream socket")


if __name__ == "__main__":
    unittest.main()
