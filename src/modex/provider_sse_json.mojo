"""Native JSON assembly policy for provider SSE data lines."""

from std.collections import List

from .json import JsonDocument
from .text import trim_text


struct ProviderSSEJSONAssembler:
    var accumulated_max_bytes: Int
    var accumulated_json: String
    var done: Bool
    var saw_done: Bool
    var failed: Bool
    var finished: Bool

    def __init__(out self, accumulated_max_bytes: Int = 4194304) raises:
        if accumulated_max_bytes < 0:
            raise Error("invalid provider SSE accumulated JSON limit")
        self.accumulated_max_bytes = accumulated_max_bytes
        self.accumulated_json = ""
        self.done = False
        self.saw_done = False
        self.failed = False
        self.finished = False

    def push(mut self, data_lines: List[String]) raises -> List[String]:
        if self.failed:
            raise Error("provider SSE assembler failed")
        if self.done or self.finished:
            return List[String]()
        for line in data_lines:
            if trim_text(line) == "[DONE]":
                self.saw_done = True
                try:
                    var result = self._flush()
                    if self.accumulated_json:
                        raise Error("incomplete JSON segment")
                    self.done = True
                    return result^
                except:
                    self.failed = True
                    raise
        try:
            return self._observe(data_lines)
        except:
            self.failed = True
            raise

    def finish(mut self) raises -> List[String]:
        if self.failed:
            raise Error("provider SSE assembler failed")
        if self.finished:
            return List[String]()
        self.finished = True
        try:
            var result = self._flush()
            if self.accumulated_json:
                self.failed = True
                raise Error("incomplete JSON segment")
            self.done = True
            return result^
        except:
            self.failed = True
            raise

    def _observe(mut self, data_lines: List[String]) raises -> List[String]:
        var joined = String()
        for index in range(len(data_lines)):
            if index:
                joined += "\n"
            joined += data_lines[index]
        var trimmed = trim_text(joined)
        if not trimmed:
            return List[String]()
        if _valid_json(trimmed):
            return _one(trimmed)

        var separate = List[String]()
        var separate_valid = True
        for line in data_lines:
            var value = trim_text(line)
            if not value:
                continue
            if not _valid_json(value):
                separate_valid = False
                break
            separate.append(value)
        if separate_valid and separate:
            return separate^

        if trimmed.byte_length() > self.accumulated_max_bytes - min(self.accumulated_json.byte_length(), self.accumulated_max_bytes):
            raise Error("provider SSE accumulated JSON exceeded safe size limit (" + String(self.accumulated_max_bytes) + ")")
        self.accumulated_json += trimmed
        return self._flush()

    def _flush(mut self) raises -> List[String]:
        var result = List[String]()
        var trimmed = trim_text(self.accumulated_json)
        if not trimmed:
            self.accumulated_json = ""
            return result^
        if _valid_json(self.accumulated_json):
            result.append(self.accumulated_json^)
            self.accumulated_json = ""
        return result^


def _one(value: String) -> List[String]:
    var result = List[String]()
    result.append(value)
    return result^


def _valid_json(value: String) -> Bool:
    try:
        var document = JsonDocument(value)
        return document.root >= 0
    except:
        return False
