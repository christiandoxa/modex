"""Capture frozen-release handling of malformed compressed session files."""

from compression import zstd
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from session_oracle import fixture, sandbox_command
from test_cli import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_zstd import NONCANONICAL, raw_frame


CASES = ("empty", "bad-magic", "truncated", "checksum", "dictionary", "window", "window-limit", "window-over-limit",
         "reserved-block", "wrong-size", "skippable-truncated", "skippable-empty", "empty-frame",
         "invalid-first-line-checksum", "invalid-first-line-short-checksum", "invalid-first-line-tiny-checksum",
         "invalid-first-line-8191-checksum", "invalid-first-line-8192-checksum", "invalid-first-line-8193-checksum",
         "invalid-first-line-raw-truncated", "invalid-first-line-raw-tiny-truncated", "invalid-utf8",
         "invalid-first-line-raw-unfinished", "invalid-first-line-flushed-unfinished", "invalid-first-line-checksum-missing")


def install_case(root, case):
    original = next((root / "home/.codex").rglob("*.jsonl"))
    content = original.read_bytes()
    encoded = zstd.compress(content)
    if case == "empty":
        encoded = b""
    elif case == "bad-magic":
        encoded = b"invalid"
    elif case == "truncated":
        encoded = encoded[:-1]
    elif case == "checksum":
        encoded = zstd.compress(content, options={zstd.CompressionParameter.checksum_flag: 1})
        encoded = encoded[:-1] + bytes([encoded[-1] ^ 1])
    elif case == "dictionary":
        encoded = raw_frame(content)
        encoded = encoded[:4] + b"\xa1\x01" + encoded[5:]
    elif case == "window":
        encoded = b"\x28\xb5\x2f\xfd\x00\x90\x01\x00\x00"
    elif case == "window-limit":
        encoded = b"\x28\xb5\x2f\xfd\x00\x88\x01\x00\x00"
    elif case == "window-over-limit":
        encoded = b"\x28\xb5\x2f\xfd\x00\x89\x01\x00\x00"
    elif case == "oversized-empty-frame":
        encoded = b"\x28\xb5\x2f\xfd\xa0\x01\x00\x00\x08\x01\x00\x00"
    elif case == "reserved-block":
        encoded = raw_frame(b"data")
        encoded = encoded[:9] + b"\x27\x00\x00" + encoded[12:]
    elif case == "wrong-size":
        encoded = raw_frame(b"data")
        encoded = encoded[:5] + b"\x05\x00\x00\x00" + encoded[9:]
    elif case == "skippable-truncated":
        encoded = b"\x50\x2a\x4d\x18\x0a\x00\x00\x00few"
    elif case == "skippable-empty":
        encoded = b"\x50\x2a\x4d\x18\x00\x00\x00\x00"
    elif case == "empty-frame":
        encoded = zstd.compress(b"")
    elif case == "invalid-utf8":
        encoded = zstd.compress(b"\xff\n")
    elif case == "noncanonical-huffman":
        encoded = NONCANONICAL.read_bytes()
    elif case == "invalid-first-line-raw-unfinished":
        encoded = bytearray(raw_frame(b"{}\n" + b"x" * 100))
        encoded[9] &= 0xFE
    elif case == "invalid-first-line-flushed-unfinished":
        compressor = zstd.ZstdCompressor()
        encoded = compressor.compress(b"{}\n" + b"x" * 100, zstd.ZstdCompressor.FLUSH_BLOCK)
    elif case == "invalid-first-line-checksum-missing":
        encoded = zstd.compress(b"{}\n" + b"x" * 100, options={zstd.CompressionParameter.checksum_flag: 1})[:-4]
    elif case.startswith("invalid-first-line-"):
        length = 200000 if case == "invalid-first-line-checksum" else 50000 if "short" in case else 100
        if case.split("-")[3].isdigit():
            length = int(case.split("-")[3]) - 3
        if "raw" in case:
            length = 100 if "tiny" in case else 50000
            encoded = raw_frame(b"{}\n" + b"x" * length)[:-10]
        else:
            encoded = zstd.compress(b"{}\n" + b"x" * length,
                                    options={zstd.CompressionParameter.checksum_flag: 1})
            encoded = encoded[:-1] + bytes([encoded[-1] ^ 1])
    original.with_suffix(".jsonl.zst").write_bytes(encoded)
    original.unlink()


def observe(binary, root):
    result = subprocess.run(sandbox_command(binary, root, ["session", "list", "--json"]),
                            capture_output=True, timeout=10, check=False)
    return {"exit_code": result.returncode,
            "stdout": result.stdout.decode().replace(str(root), "<FIXTURE_ROOT>"),
            "stderr": result.stderr.decode().replace(str(root), "<FIXTURE_ROOT>")}


def main():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("The oracle checksum does not match the frozen release")
    records = []
    differences = []
    with tempfile.TemporaryDirectory(prefix="modex-zstd-oracle-") as directory:
        for case in CASES:
            root = Path(directory) / case
            root.mkdir()
            fixture(root)
            install_case(root, case)
            record = {"case": case, **observe(ORACLE, root)}
            records.append(record)
            print(case, record["exit_code"], repr(record["stderr"]))
        for case in ("noncanonical-huffman", "oversized-empty-frame"):
            observations = {}
            for label, binary in (("baseline", ORACLE), ("modex", MODEX)):
                root = Path(directory) / (case + "-" + label)
                root.mkdir()
                fixture(root)
                install_case(root, case)
                observations[label] = observe(binary, root)
            record = {"case": case, "observations": observations, "status": "UNAPPROVED_DIFFERENCE"}
            if case == "noncanonical-huffman":
                record.update({"input": str(NONCANONICAL.relative_to(ROOT)),
                    "input_sha256": hashlib.sha256(NONCANONICAL.read_bytes()).hexdigest(),
                    "reason": "The release accepts leftover Huffman bits despite RFC 8878 section 4.2.2; Modex rejects the noncanonical stream. The released session command reaches UTF-8 validation instead."})
            else:
                record.update({"input_hex": "28b52ffda001000008010000",
                    "reason": "The release accepts an empty frame declaring 134217729 decoded bytes. Modex rejects its oversized window; decoded content size and window validation are retained pending separate approval."})
            differences.append(record)
    output = ROOT / "docs/evidence/baseline/session-zstd-errors.json"
    output.write_text(json.dumps({"schema_version": 1, "oracle_sha256": ORACLE_SHA256,
        "baseline_commit": "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3",
        "reproduce": "python3 tests/capture_session_zstd.py", "cases": records,
        "known_differences": differences}, indent=2) + "\n")


if __name__ == "__main__":
    main()
