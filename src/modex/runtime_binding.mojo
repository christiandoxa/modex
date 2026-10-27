"""Provider ownership for accepted local-rewrite continuations."""

from std.collections import List

from .sha256 import SHA256
from .text import trim_text


def _binding_digest(kind: String, value: String) raises -> String:
    var hash = SHA256()
    hash.update("prodex-runtime-binding-v1\x00".as_bytes())
    hash.update(kind.as_bytes())
    hash.update("\x00".as_bytes())
    hash.update(value.as_bytes())
    return "sha256:" + hash.hex_digest()


@fieldwise_init
struct RuntimeProviderIdentity(Copyable):
    var provider: String
    var credential: String
    var endpoint: String
    var profile: String


def _identity(credential: String, endpoint: String, profile: String) raises -> RuntimeProviderIdentity:
    return RuntimeProviderIdentity(
        "deepseek", _binding_digest("credential", credential),
        _binding_digest("endpoint", endpoint),
        _binding_digest("profile", profile) if profile else String(),
    )


def _same_identity(left: RuntimeProviderIdentity, right: RuntimeProviderIdentity) -> Bool:
    return left.provider == right.provider and left.credential == right.credential and left.endpoint == right.endpoint and left.profile == right.profile


def _binding_key_valid(value: String) -> Bool:
    if not value or value.byte_length() > 1024:
        return False
    for character in value.codepoints():
        var codepoint = Int(character)
        if codepoint <= 31 or 127 <= codepoint <= 159:
            return False
    return True


@fieldwise_init
struct RuntimeBinding(Copyable):
    var kind: Int
    var key: String
    var identity: RuntimeProviderIdentity
    var conflict: Bool
    var sequence: UInt64


# shortcut: bindings are in memory only; persist them when profile state is connected.
struct RuntimeBindings:
    var accepted: RuntimeProviderIdentity
    var selected: RuntimeProviderIdentity
    var rows: List[RuntimeBinding]
    var sequence: UInt64

    def __init__(out self, key: String, endpoint: String) raises:
        self.accepted = _identity(key, endpoint, "")
        self.selected = _identity("local", endpoint, "local")
        self.rows = List[RuntimeBinding]()
        self.sequence = 0

    def permits(self, previous: String, turn: String, session: String) -> Bool:
        for row in self.rows:
            if (row.kind == 0 and row.key == previous or row.kind == 1 and row.key == turn or row.kind == 2 and row.key == session):
                if row.conflict or not _same_identity(row.identity, self.selected):
                    return False
        return True

    def remember(mut self, kind: Int, var key: String):
        key = trim_text(key)
        if not _binding_key_valid(key):
            return
        if self.sequence < UInt64.MAX:
            self.sequence += 1
        for index in range(len(self.rows)):
            if self.rows[index].kind == kind and self.rows[index].key == key:
                if not _same_identity(self.rows[index].identity, self.accepted):
                    self.rows[index].conflict = True
                self.rows[index].sequence = self.sequence
                return
        var limit = 16384 if kind == 0 else 2048
        var count = 0
        var oldest = -1
        for index in range(len(self.rows)):
            if self.rows[index].kind == kind:
                count += 1
                if oldest < 0 or self.rows[index].sequence < self.rows[oldest].sequence:
                    oldest = index
        if count >= limit:
            _ = self.rows.pop(oldest)
        self.rows.append(RuntimeBinding(kind, key^, self.accepted.copy(), False, self.sequence))

    def remember_request(mut self, previous: String, turn: String, session: String):
        self.remember(0, previous)
        self.remember(1, turn)
        self.remember(2, session)
