"""Deterministic native differential fuzzing for streaming SSE ID observation."""

import json
import os
import random
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER_SOURCE = ROOT / "tests/runtime_observer_fuzz_driver.mojo"
EXPECTED_OLD_PATH_DIFFERENCES = {"oracle-nbsp-data-prefix"}


def quoted(value, ascii_only=True):
    return json.dumps(value, ensure_ascii=ascii_only, separators=(",", ":"))


def object_text(fields):
    return "{" + ",".join(quoted(key) + ":" + value for key, value in fields) + "}"


def random_value(rng, depth=0):
    choices = ("null", "bool", "number", "string") if depth >= 4 else (
        "null", "bool", "number", "string", "array", "object"
    )
    kind = rng.choice(choices)
    if kind == "null":
        return "null"
    if kind == "bool":
        return rng.choice(("true", "false"))
    if kind == "number":
        return rng.choice((
            "0", "-0", "1", "-12", "18446744073709551615",
            "18446744073709551616", "9007199254740993.0", "1.7976931348623157e308",
            "2.2250738585072014e-308", "4.9406564584124654e-324", "1e-400",
        ))
    if kind == "string":
        alphabet = 'aZ09_ /\\"\n\té雪🔥\u2028\u00a0'
        return quoted("".join(rng.choice(alphabet) for _ in range(rng.randrange(18))),
                      ascii_only=bool(rng.randrange(2)))
    if kind == "array":
        return "[" + ",".join(random_value(rng, depth + 1)
                               for _ in range(rng.randrange(5))) + "]"
    fields = []
    for _ in range(rng.randrange(5)):
        fields.append(("field" + str(rng.randrange(4)), random_value(rng, depth + 1)))
    return object_text(fields)


def valid_documents(rng, count):
    documents = []
    ids = ("resp-basic", " leading ", "resp_é_東京_🔥", "", "\u00a0trim\u2003",
           "quote\\slash/", "x" * rng.randrange(1, 30))
    target_keys = ("id", "response_id", "responseId", "message", "response")
    for index in range(count):
        response = object_text([
            ("noise", random_value(rng)),
            ("id", quoted(rng.choice(ids), ascii_only=bool(rng.randrange(2)))),
            ("id", random_value(rng) if rng.randrange(4) == 0 else
             quoted("resp-dup-" + str(index))),
        ])
        fields = [("noise" + str(item), random_value(rng))
                  for item in range(rng.randrange(4))]
        fields += [("response", response)]
        for _ in range(rng.randrange(3)):
            key = rng.choice(target_keys)
            if key == "response":
                value = rng.choice((response, "null", "[]", random_value(rng)))
            elif key == "message":
                value = object_text([("id", quoted("resp-msg-" + str(index)))])
            elif key == "id":
                value = rng.choice((quoted("resp-root-" + str(index)), "0", "null"))
            else:
                value = rng.choice((quoted("resp-fallback-" + str(index)), "false"))
            fields.append((key, value))
        documents.append(object_text(fields))
    return documents


def data_wire(payload, rng, multiline=False):
    newline = rng.choice((b"\n", b"\r\n"))
    chunks = [payload]
    if multiline and payload:
        text = payload.decode("utf-8")
        safe = []
        in_string = False
        escaped = False
        for index, char in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in ",:{}[]":
                safe.append(index + 1)
        if safe:
            cut = rng.choice(safe)
            chunks = [text[:cut].encode(), text[cut:].encode()]
    lines = [b": fuzz comment", b"event: response.completed", b"id: ignored"]
    lines.extend(b"data: " + chunk for chunk in chunks)
    return newline.join(lines) + newline + newline


def random_schedule(length, rng, index):
    if length == 0:
        return [1]
    if index % 17 == 0:
        return [1] * length
    if index % 5 == 0:
        result = []
        remaining = length
        for amount in (2, 3, 5, 7, 11, 13, 17):
            if not remaining:
                break
            amount = min(amount, remaining)
            result.append(amount)
            remaining -= amount
        if remaining:
            result.append(remaining)
        return result
    result = []
    remaining = length
    while remaining:
        amount = rng.randint(1, min(31, remaining))
        result.append(amount)
        remaining -= amount
    return result


def compact_result(result):
    status, identifiers = result
    values = [value if len(value) <= 64 else value[:32] + "…<" + str(len(value)) + ">"
              for value in identifiers]
    return status, values


def make_cases():
    rng = random.Random(0x04392_5EED)
    cases = []

    def add(label, wire, schedule=None):
        index = len(cases)
        schedule = schedule or random_schedule(len(wire), rng, index)
        cases.append((label, wire, schedule))

    documents = [
        b'{"response":{"id":"resp-basic"}}',
        b'{"response":{"id":"old","id":"resp-last"}}',
        b'{"response":{"id":"resp-stale"},"response":{},"id":"resp-root"}',
        b'{"response":{"id":12},"id":"resp-fallback"}',
        b'{"response":null,"response_id":"resp-snake"}',
        b'{"response":[],"responseId":"resp-camel"}',
        b'{"message":{"id":"resp-message"}}',
        b'{"other":{"id":"resp-decoy"},"response":{"meta":{"id":"resp-decoy"}}}',
        b'{"res\\u0070onse":{"id":"resp-escaped-key"}}',
        b'{"response":{"id":"resp\\u002fescape\\\\quote\\\""}}',
        '{"response":{"id":"resp-東京-🔥"}}'.encode(),
        b'{"response":{"id":" leading and trailing "}}',
        b'{"response":{"id":"resp"},"v":[0,-0,1.2e+3,-2.5E-2]}',
        b'{"response":{"id":"resp"},"v":18446744073709551615}',
        b'{"response":{"id":"resp"},"v":9007199254740993.0}',
        b'{"response":{"id":"resp"},"v":1.7976931348623157e308}',
        b'{"response":{"id":"resp"},"v":2.2250738585072014e-308}',
        b'{"response":{"id":"resp"},"v":4.9406564584124654e-324}',
        b'{"response":{"id":"resp"},"v":0.' + b"0" * 256 + b"1}",
        b'{"response":{"id":"resp"},"v":1' + b"0" * 256 + b"e-256}",
        b'{"response":{"id":"resp"},"v":1' + b"0" * 256 + b"e9999}",
        b'{"response":{"id":"resp"},"v":1e9999}',
        b'{"response":{"id":"resp"},"v":01}',
        b'{"response":{"id":"resp"},"v":1.}',
        b'{"response":{"id":"resp"},"v":1e+}',
        b'{"response":{"id":"resp"},"v":"\\uD800"}',
        b'{"response":{"id":"resp"},"v":"\\uDC00"}',
        b'{"response":{"id":"resp"},"v":"\\q"}',
        b'{"response":{"id":"resp"}}x',
        b'{"response":{"id":"resp"} "x":1}',
        b'{"response":{"id":"resp"},}',
        b'{"response":{"id":"resp"}',
        b'[ {"response":{"id":"resp-array-decoy"}} ]',
    ]
    for index, document in enumerate(documents):
        add("fixed-json-" + str(index), data_wire(document, rng, multiline=index % 3 == 0))

    for depth in (0, 1, 7, 31, 124, 125, 126, 127, 128):
        document = ('{"response":{"id":"resp-depth"},"deep":' +
                    "[" * depth + "0" + "]" * depth + "}").encode()
        add("depth-" + str(depth), data_wire(document, rng))

    for length in (0, 1, 31, 1023, 1024, 1025):
        document = b'{"response":{"id":"' + b"x" * length + b'"}}'
        wire = data_wire(document, rng)
        add("identifier-bytes-" + str(length), wire,
            [1] * len(wire) if length == 1025 else None)

    invalid_utf8 = (
        b'data: {"response":{"id":"resp"},"x":"\xff"}\n\n',
        b'data: {"response":{"id":"resp"},"x":"\xc0\x80"}\n\n',
        b'data: {"response":{"id":"resp"},"x":"\xed\xa0\x80"}\n\n',
        b'data: {"response":{"id":"resp"},"x":"\xf4\x90\x80\x80"}\n\n',
        b'data: {"response":{"id":"resp"},"x":"\xe2\x82',
        b'data: {"response":{"id":"before"}}\n\n'
        b'data: {"response":{"id":"resp"},"x":"\xff"}\n\n',
    )
    for index, wire in enumerate(invalid_utf8):
        add("utf8-" + str(index), wire)

    add("oracle-nbsp-data-prefix",
        b'event: response.completed\ndata:' + "\u00a0".encode()
        + b'{"response":{"id":"resp_nbsp"}}\n\n')

    for index, document in enumerate(valid_documents(rng, 360)):
        wire = data_wire(document.encode(), rng, multiline=index % 4 == 0)
        add("random-valid-" + str(index), wire)

    malformed_suffixes = (b"x", b"  x", b",", b"}", b"\x00", b"\xff", b"01", b"1e+",
                          b'"\\uD800"', b'"\\q"')
    for index in range(120):
        prefix = object_text([("response", object_text([("id", quoted("resp-mut-" + str(index)))]))]).encode()
        suffix = rng.choice(malformed_suffixes)
        wire = data_wire(prefix[:-1] + suffix + prefix[-1:], rng)
        add("random-invalid-" + str(index), wire)

    for index in range(36):
        first = object_text([("response", object_text([("id", quoted("resp-first-" + str(index)))]))]).encode()
        second = object_text([("id", quoted("resp-second-" + str(index))),
                              ("response", random_value(rng))]).encode()
        wire = data_wire(first, rng) + data_wire(second, rng)
        add("two-events-" + str(index), wire)
    return cases


class RuntimeObserverFuzzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._build = tempfile.TemporaryDirectory(prefix="modex-observer-fuzz-build-")
        cls.addClassCleanup(cls._build.cleanup)
        build_dir = Path(cls._build.name)
        cls.driver = build_dir / "runtime-observer-fuzz-driver"
        command = [os.environ.get("MOJO", "mojo"), "build", "-O3",
                   "--target-cpu=x86-64-v3", "-I", str(ROOT / "src"),
                   str(DRIVER_SOURCE), "-o", str(cls.driver)]
        environment = os.environ.copy()
        environment["TMPDIR"] = str(build_dir)
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                timeout=180, check=False)
        if result.returncode or not cls.driver.is_file():
            raise AssertionError(
                f"native driver build failed ({result.returncode}):\n"
                f"{result.stdout.decode(errors='replace')}\n{result.stderr.decode(errors='replace')}"
            )

    def test_adversarial_and_seeded_streams_match_old_selection(self):
        cases = make_cases()
        self.assertEqual(len(cases), 571)
        wire = b"".join(
            (",".join(map(str, schedule)) + ":" + payload.hex() + "\n").encode()
            for _, payload, schedule in cases
        )
        result = subprocess.run([str(self.driver)], input=wire, capture_output=True,
                                timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        rows = result.stdout.decode("utf-8").split("\n")
        if rows and rows[-1] == "":
            rows.pop()
        self.assertEqual(len(rows), len(cases), "native driver omitted a case result")

        mismatches = []
        expected_differences = set()
        for case, row in zip(cases, rows, strict=True):
            label, payload, schedule = case
            fields = row.split("\t")
            self.assertEqual(len(fields), 6, (label, row))
            old_status, old_raw = fields[0], json.loads(fields[1])
            old_bindings = json.loads(fields[2])
            new_status, new_raw = fields[3], json.loads(fields[4])
            new_bindings = json.loads(fields[5])

            # The real release accepts this exact NBSP data prefix; the older
            # JsonDocument helper rejects it because it only parses ASCII JSON whitespace.
            if label in EXPECTED_OLD_PATH_DIFFERENCES:
                self.assertEqual((old_status, old_raw, old_bindings,
                                  new_status, new_raw, new_bindings),
                                 ("OK", [], [], "OK", ["resp_nbsp"], ["resp_nbsp"]))
                expected_differences.add(label)
                continue

            if label == "identifier-bytes-1025":
                self.assertEqual(old_raw, ["x" * 1025])
                self.assertEqual(new_raw, [])
                self.assertEqual(old_bindings, [])
                self.assertEqual(new_bindings, [])

            old = (old_status, old_bindings)
            new = (new_status, new_bindings)
            if old != new:
                mismatches.append((label, compact_result(old), compact_result(new),
                                   len(payload), payload[:64], schedule[:16]))
        self.assertEqual(expected_differences, EXPECTED_OLD_PATH_DIFFERENCES,
                         "oracle-backed old-path difference was not exercised")
        message = ""
        if mismatches:
            first = mismatches[0]
            message = (
                "old ProviderSSEFramer + JsonDocument differs from "
                f"RuntimeSSEBindingObserver in {len(mismatches)} of {len(cases)} cases; "
                f"first={first[0]!r}, old={first[1]!r}, new={first[2]!r}, "
                f"wire length={first[3]}, prefix={first[4]!r}, schedule prefix={first[5]!r}"
            )
        self.assertFalse(mismatches, message)


if __name__ == "__main__":
    unittest.main()
