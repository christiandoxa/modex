"""Frozen Super hook-trust JSON-RPC sequence, independent of process transport."""

from std.collections import List, Span

from .json import JSON_ARRAY, JSON_NUMBER, JSON_STRING, JsonDocument, quote_json

comptime HOOK_TRUST_RPC_TIMEOUT_MS = 12000
# shortcut: 16 MiB per JSON-RPC line, raise only for a verified larger Codex frame.
comptime HOOK_TRUST_MAX_RPC_LINE_BYTES = 16777216
comptime HOOK_TRUST_MAX_HOOKS = 65536
comptime HOOK_TRUST_MAX_STATUS_BYTES = 65536


def _i64(doc: JsonDocument, node: Int) -> Optional[Int64]:
    if node < 0 or doc.nodes[node].kind != JSON_NUMBER:
        return Optional[Int64]()
    var text = doc.nodes[node].text
    if "." in text or "e" in text or "E" in text or text == "-0":
        return Optional[Int64]()
    var negative = text.startswith("-")
    var digits = String(text[byte=1:]) if negative else text
    var limit = UInt64(9223372036854775808) if negative else UInt64(Int64.MAX)
    var magnitude = UInt64(0)
    for byte in digits.as_bytes():
        var digit = UInt64(byte - 48)
        if magnitude > (limit - digit) // 10:
            return Optional[Int64]()
        magnitude = magnitude * 10 + digit
    if negative:
        return Int64.MIN if magnitude == UInt64(9223372036854775808) else -Int64(magnitude)
    return Int64(magnitude)


def _list_entries(doc: JsonDocument, listed: Int) raises -> Int:
    var entries = doc.get(listed, "data")
    if entries < 0 or doc.nodes[entries].kind != JSON_ARRAY:
        raise Error("Codex hooks/list response omitted data")
    return entries


def _validate_diagnostics(doc: JsonDocument, entries: Int) raises:
    for entry in doc.nodes[entries].children:
        for field in ["warnings", "errors"]:
            var messages = doc.get(entry, field)
            if messages < 0 or doc.nodes[messages].kind != JSON_ARRAY:
                continue
            var rendered = String()
            var count = 0
            for message in doc.nodes[messages].children:
                if doc.nodes[message].kind != JSON_STRING:
                    continue
                if count: rendered += "; "
                rendered += doc.string(message)
                count += 1
            if count:
                raise Error("Codex hooks/list reported " + field + ": " + rendered)


def _untrusted_hooks(doc: JsonDocument, entry: Int) raises -> List[Int]:
    var hooks = doc.get(entry, "hooks")
    if hooks < 0 or doc.nodes[hooks].kind != JSON_ARRAY:
        raise Error("Codex hooks/list entry omitted hooks")
    if len(doc.nodes[hooks].children) > HOOK_TRUST_MAX_HOOKS:
        raise Error("compiled Mojo hook trust selection rejected oversized input")
    var selected = List[Int]()
    for hook in doc.nodes[hooks].children:
        var status = doc.string(doc.get(hook, "trustStatus"))
        if status.byte_length() > HOOK_TRUST_MAX_STATUS_BYTES:
            # shortcut: the frozen host panics here; preserve rejection until panic parity is implemented.
            raise Error("compiled Mojo hook trust selection rejected oversized input")
        if status == "untrusted" or status == "modified":
            selected.append(hook)
    return selected^


def hook_trust_updates(doc: JsonDocument, listed: Int) raises -> String:
    var entries = _list_entries(doc, listed)
    _validate_diagnostics(doc, entries)
    var updates = List[Tuple[String, Int]]()
    for entry in doc.nodes[entries].children:
        var selected = _untrusted_hooks(doc, entry)
        for hook in selected:
            var key = doc.string(doc.get(hook, "key"))
            if not key:
                raise Error("Codex hooks/list returned a trustable hook without key")
            if not doc.string(doc.get(hook, "currentHash")):
                raise Error("Codex hooks/list returned a trustable hook without currentHash")
            updates.append((key, hook))
    sort(Span(updates), lambda (left: Tuple[String, Int], right: Tuple[String, Int]) -> Bool:
         left[0] < right[0] or left[0] == right[0] and left[1] < right[1])
    var output = String("{")
    var count = 0
    for index in range(len(updates)):
        if index + 1 < len(updates) and updates[index][0] == updates[index + 1][0]:
            continue
        if count: output += ","
        output += quote_json(updates[index][0]) + ':{"trusted_hash":' + quote_json(doc.string(doc.get(updates[index][1], "currentHash"))) + "}"
        count += 1
    return output + "}"


def verify_hooks_trusted(doc: JsonDocument, listed: Int) raises:
    var entries = _list_entries(doc, listed)
    _validate_diagnostics(doc, entries)
    for entry in doc.nodes[entries].children:
        var selected = _untrusted_hooks(doc, entry)
        if selected:
            var key = doc.get(selected[0], "key")
            var label = doc.string(key) if key >= 0 and doc.nodes[key].kind == JSON_STRING else String("<unknown>")
            raise Error("Codex hook remained untrusted after Super preflight: " + label)


struct HookTrustSession:
    var workspace: String
    var phase: Int
    var updates: String
    var done: Bool
    var legacy: Bool

    def __init__(out self, workspace: String):
        self.workspace = workspace
        self.phase = 1
        self.updates = "{}"
        self.done = False
        self.legacy = False

    def method(self) -> String:
        return "initialize" if self.phase == 1 else "config/batchWrite" if self.phase == 3 else "hooks/list"

    def operation(self) -> String:
        return "hooks/list verification" if self.phase == 4 else self.method()

    def timeout_message(self) -> String:
        return "Codex hook-trust preflight timed out waiting for " + self.method()

    def request(self) raises -> String:
        if self.done:
            raise Error("hook-trust preflight is already complete")
        var params: String
        if self.phase == 1:
            params = '{"capabilities":{"experimentalApi":true},"clientInfo":{"name":"prodex-hook-trust","version":"0.439.2"}}'
        elif self.phase == 3:
            params = '{"edits":[{"keyPath":"hooks.state","mergeStrategy":"upsert","value":' + self.updates + '}],"expectedVersion":null,"filePath":null,"reloadUserConfig":true}'
        else:
            params = '{"cwds":[' + quote_json(self.workspace) + "]}"
        return '{"id":' + String(self.phase) + ',"jsonrpc":"2.0","method":' + quote_json(self.method()) + ',"params":' + params + "}"

    def accept(mut self, line: String) raises -> Bool:
        if self.done:
            raise Error("hook-trust preflight is already complete")
        var doc: JsonDocument
        try:
            doc = JsonDocument(line)
        except:
            return False
        var id = _i64(doc, doc.get(doc.root, "id"))
        if not id or id.value() != Int64(self.phase):
            return False
        var error = doc.get(doc.root, "error")
        if error >= 0:
            var code = _i64(doc, doc.get(error, "code"))
            var number = code.value() if code else Int64(0)
            if number == -32601 and (self.phase == 2 or self.phase == 3):
                self.done = True
                self.legacy = True
                return True
            var message = doc.get(error, "message")
            var text = doc.string(message) if message >= 0 and doc.nodes[message].kind == JSON_STRING else String("unknown JSON-RPC error")
            raise Error("Codex hook-trust " + self.operation() + " failed (" + String(number) + "): " + text)
        var result = doc.get(doc.root, "result")
        if result < 0:
            raise Error("Codex hook-trust response omitted result")
        if self.phase == 1:
            self.phase = 2
        elif self.phase == 2:
            self.updates = hook_trust_updates(doc, result)
            self.phase = 4 if self.updates == "{}" else 3
        elif self.phase == 3:
            var status_node = doc.get(result, "status")
            var status = doc.string(status_node)
            if status.byte_length() > HOOK_TRUST_MAX_STATUS_BYTES:
                raise Error("compiled Mojo hook config-write classification rejected oversized input")
            if status != "ok" and status != "okOverridden":
                var label = status if status_node >= 0 and doc.nodes[status_node].kind == JSON_STRING else String("<missing>")
                raise Error("Codex hook-trust config write did not report a successful status: " + label)
            self.phase = 4
        else:
            verify_hooks_trusted(doc, result)
            self.done = True
        return True
