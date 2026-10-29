# Plain runtime log field parsing

Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) use a token plan for plain
runtime log lines that finds the first non-field event even after fields, skips
empty unquoted field values, and keeps quoted values together. Their runtime
proxy parser decodes valid JSON string values and falls back to trimming quotes
for invalid quoted values. Later duplicate fields replace earlier fields.

Before this change, Modex assumed the event was the first token and split values
at whitespace. Real-process comparisons showed that a leading `request=7`
caused upstream and token events to disappear, and a quoted `profile="hello
world"` became `"hello`. The shared runtime-record parser now follows the plain
log token plan, while retaining the existing event-specific selection and
redaction checks.

`tests/test_log_plain_parser_01651_04392.py` uses checksum-pinned release
binaries and synthetic, isolated file-backed fixtures. It compares JSON and
plain `log last` output for reordered fields, quoted and malformed values,
empty values, duplicate keys, upstream payloads, and token usage. It also
compares followed upstream, stream, and token records. These selected Linux
x86-64 observations do not establish live-source, security, or six-target parity.
