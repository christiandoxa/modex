"""Incremental provider bytes through JSON assembly and chat event translation."""

from std.collections import List

from .provider_chat_stream import DeepSeekChatState
from .provider_sse_json import ProviderSSEJSONAssembler
from .provider_sse_wire import ProviderSSEFramer


struct DeepSeekChatReader:
    var framer: ProviderSSEFramer
    var assembler: ProviderSSEJSONAssembler
    var state: DeepSeekChatState
    var native_messages: Bool
    var done: Bool

    def __init__(out self, request_id: UInt64, response_id: String, created_at: UInt64, request_metadata: String = "null", line_max_bytes: Int = 4194304, event_max_bytes: Int = 4194304, accumulated_max_bytes: Int = 4194304, native_messages: Bool = False) raises:
        self.framer = ProviderSSEFramer(line_max_bytes, event_max_bytes)
        self.assembler = ProviderSSEJSONAssembler(accumulated_max_bytes)
        self.state = DeepSeekChatState(request_id, response_id, created_at, request_metadata)
        self.native_messages = native_messages
        self.done = False

    def consume(mut self, chunk: ImmSpan[UInt8, _]) raises -> Tuple[Int, List[String]]:
        var output = List[String]()
        if self.done:
            return (0, output^)
        var used = len(chunk)
        try:
            var framed = self.framer.consume(chunk)
            used = framed[0]
            if framed[1]:
                output.extend(self.frame(framed[1].value()))
            return (used, output^)
        except error:
            if self.state.completed and not self.assembler.saw_done:
                raise
            self.done = True
            output.extend(self.state.fail("provider_stream_error", String(error)))
            return (used, output^)

    def frame(mut self, lines: List[String]) raises -> List[String]:
        var output = List[String]()
        for value in self.assembler.push(lines):
            output.extend(self.state.observe_anthropic(value) if self.native_messages else self.state.observe(value))
            if self.native_messages and self.state.anthropic_stream_terminal:
                self.done = True
                return output^
        if self.assembler.done:
            if self.native_messages:
                output.extend(self.state.fail("provider_stream_error", "unexpected end of stream"))
            else:
                output.extend(self.state.complete())
            self.done = True
        return output^

    def finish(mut self) raises -> List[String]:
        var output = List[String]()
        if self.done:
            return output^
        var framed: Optional[List[String]]
        try:
            framed = self.framer.finish()
        except error:
            if self.state.completed:
                raise
            self.done = True
            return self.state.fail("provider_stream_error", String(error))
        if framed:
            try:
                output.extend(self.frame(framed.value()))
            except error:
                if self.state.completed and not self.assembler.saw_done:
                    raise
                self.done = True
                output.extend(self.state.fail("provider_stream_error", String(error)))
                return output^
        if self.done:
            return output^
        self.done = True
        try:
            for value in self.assembler.finish():
                output.extend(self.state.observe_anthropic(value) if self.native_messages else self.state.observe(value))
        except error:
            output.extend(self.state.fail("provider_stream_error", String(error)))
            return output^
        output.extend(self.state.fail("provider_stream_error", "unexpected end of stream"))
        return output^
