"""Bounded byte framer for provider-sent events."""

from std.collections import List


def decode_provider_sse_utf8(bytes: List[UInt8]) raises -> String:
    try:
        return String(from_utf8=Span(bytes))
    except:
        raise Error("stream did not contain valid UTF-8")


struct ProviderSSEFramer:
    var line_max_bytes: Int
    var event_max_bytes: Int
    var inspection: Bool
    var line: List[UInt8]
    var data: List[String]
    var invalid_event: Bool
    var event_bytes: Int
    var failed: Bool
    var finished: Bool

    def __init__(out self, line_max_bytes: Int = 4194304, event_max_bytes: Int = 4194304, inspection: Bool = False) raises:
        if line_max_bytes <= 0 or event_max_bytes <= 0:
            raise Error("provider SSE limits must be positive and bounded")
        self.line_max_bytes = line_max_bytes
        self.event_max_bytes = event_max_bytes
        self.inspection = inspection
        self.line = List[UInt8]()
        self.data = List[String]()
        self.invalid_event = False
        self.event_bytes = 0
        self.failed = False
        self.finished = False

    def consume(mut self, chunk: ImmSpan[UInt8, _]) raises -> Tuple[Int, Optional[List[String]]]:
        if self.failed:
            raise Error("provider SSE framer is failed")
        if self.finished:
            raise Error("provider SSE framer is finished")
        var used = 0
        try:
            while used < len(chunk):
                var byte = chunk[used]
                self.line.append(byte)
                used += 1
                if len(self.line) > self.line_max_bytes:
                    # Match read_line's UTF-8 validation before its size check.
                    _ = decode_provider_sse_utf8(self.line)
                    raise Error("provider SSE line exceeded safe size limit (" + String(self.line_max_bytes) + ")")
                if byte == 10:
                    var frame = self.process_line()
                    if frame:
                        return (used, frame^)
            return (used, Optional[List[String]]())
        except:
            self.failed = True
            raise

    def finish(mut self) raises -> Optional[List[String]]:
        if self.failed:
            raise Error("provider SSE framer is failed")
        if self.finished:
            return Optional[List[String]]()
        try:
            self.finished = True
            if self.line:
                var frame = self.process_line()
                if frame:
                    return frame^
            if self.data:
                var output = self.data^
                self.data = List[String]()
                return output^
            return Optional[List[String]]()
        except:
            self.failed = True
            raise

    def process_line(mut self) raises -> Optional[List[String]]:
        var end = len(self.line)
        while end > 0 and (self.line[end - 1] == 10 or self.line[end - 1] == 13):
            end -= 1
        var raw = List[UInt8]()
        for i in range(end):
            raw.append(self.line[i])
        self.line.clear()
        # The release scanner classifies raw fields before validating data bytes.
        if not self.inspection:
            _ = decode_provider_sse_utf8(raw)
        if end == 0:
            if self.invalid_event:
                self.invalid_event = False
                self.data.clear()
                self.event_bytes = 0
                return Optional[List[String]]()
            if self.data:
                var output = self.data^
                self.data = List[String]()
                self.event_bytes = 0
                return output^
            self.event_bytes = 0
            return Optional[List[String]]()
        var colon = -1
        for i in range(end):
            if raw[i] == 58:
                colon = i
                break
        var field_end = end if colon < 0 else colon
        if field_end != 4 or raw[0] != 100 or raw[1] != 97 or raw[2] != 116 or raw[3] != 97:
            return Optional[List[String]]()
        if self.invalid_event:
            return Optional[List[String]]()
        var start = end
        if colon >= 0:
            start = colon + 1
            if start < end and raw[start] == 32:
                start += 1
        var value_bytes = List[UInt8]()
        for i in range(start, end):
            value_bytes.append(raw[i])
        var value: String
        try:
            value = decode_provider_sse_utf8(value_bytes)
        except:
            if not self.inspection:
                raise
            self.invalid_event = True
            self.data.clear()
            self.event_bytes = 0
            return Optional[List[String]]()
        self.append_data(value)
        return Optional[List[String]]()

    def append_data(mut self, value: String) raises:
        var size = value.byte_length()
        if size >= self.event_max_bytes - self.event_bytes:
            raise Error("provider SSE event exceeded safe size limit (" + String(self.event_max_bytes) + ")")
        self.event_bytes += size + 1
        self.data.append(value)
