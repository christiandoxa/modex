"""Readable display for decoded upstream payload bytes."""

from std.collections import List, Span

from .log_text import trim_unicode
from .zstd import ZstdReader

comptime MAX_DECODED_UPSTREAM_PAYLOAD_BYTES = 128 * 1024


def readable_upstream_payload(payload: List[UInt8], paths: List[String], present: List[Bool]) raises -> String:
    if readable_text(payload):
        return String(from_utf8=Span(payload))
    var kind = binary_label(payload)
    if is_magic(payload, [0x28, 0xB5, 0x2F, 0xFD]):
        try:
            var decoder = ZstdReader(payload)
            var decoded = List[UInt8]()
            var complete = False
            while True:
                var chunk = decoder.read_chunk()
                if not chunk:
                    complete = True
                    break
                if len(decoded) + len(chunk) > MAX_DECODED_UPSTREAM_PAYLOAD_BYTES:
                    break
                decoded.extend(chunk^)
            if complete and readable_text(decoded):
                return String(from_utf8=Span(decoded))
        except:
            pass
    for index in range(min(len(paths), len(present))):
        if present[index]:
            var trimmed = trim_unicode(paths[index])
            if trimmed:
                return "[binary payload: path=" + trimmed + "]"
            break
    return "[binary payload: " + kind + "]"


def readable_text(bytes: List[UInt8]) -> Bool:
    var text: String
    try:
        text = String(from_utf8=Span(bytes))
    except:
        return False
    for character in text.codepoints():
        var code = Int(character)
        if code < 32 and code != 9 and code != 10 and code != 13:
            return False
        if 0x7F <= code <= 0x9F:
            return False
    return True


def is_magic(bytes: List[UInt8], magic: List[Int]) -> Bool:
    if len(bytes) < len(magic):
        return False
    for index in range(len(magic)):
        if Int(bytes[index]) != magic[index]:
            return False
    return True


def binary_label(bytes: List[UInt8]) -> String:
    if is_magic(bytes, [137, 80, 78, 71, 13, 10, 26, 10]): return "PNG image"
    if is_magic(bytes, [255, 216, 255]): return "JPEG image"
    if is_magic(bytes, [71, 73, 70, 56, 55, 97]) or is_magic(bytes, [71, 73, 70, 56, 57, 97]): return "GIF image"
    if is_magic(bytes, [37, 80, 68, 70, 45]): return "PDF document"
    if is_magic(bytes, [80, 75, 3, 4]): return "ZIP archive"
    if is_magic(bytes, [31, 139]): return "gzip stream"
    if is_magic(bytes, [40, 181, 47, 253]): return "zstd stream"
    if len(bytes) >= 12 and is_magic(bytes, [82, 73, 70, 70]) and String(from_utf8_lossy=Span(bytes)[8:12]) == "WEBP": return "WebP image"
    return "unknown binary data"
