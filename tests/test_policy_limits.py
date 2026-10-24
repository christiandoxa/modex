"""Oracle checks for policy parsing near TOML recursion and size boundaries."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import ORACLE


MODEX = test_cli.MODEX
TOKEN_EVENT = b'{"timestamp":"2026-10-24T01:02:04Z","event":"token_usage","fields":{"input_tokens":"101","output_tokens":"4"}}\n'
TMP_EVENT = b'{"timestamp":"2026-10-24T01:02:04Z","event":"token_usage","fields":{"input_tokens":"202","output_tokens":"4"}}\n'


def nested_array(depth):
    return "[" * depth + '"x"' + "]" * depth


def mixed_nested_value(depth):
    value = '"x"'
    for index in range(depth):
        value = f"[{value}]" if index % 2 == 0 else "{k=" + value + "}"
    return value


def nested_inline(depth, leaf='"x"'):
    value = leaf
    for _ in range(depth):
        value = "{k=" + value + "}"
    return value


def nested_dotted_inline(value_depth, key_depth, arrays=False):
    path = ".".join(["k"] * key_depth)
    value = '"x"'
    for _ in range(value_depth):
        value = f"[{{{path}={value}}}]" if arrays else f"{{{path}={value}}}"
    return value


def dotted_key(depth):
    return ".".join(["future"] * depth)


def run(binary, policy, base, label):
    root = base / label
    home = root / "home"
    prodex = root / ".prodex"
    temporary = root / "tmp"
    workspace = root / "workspace"
    home.mkdir(parents=True, mode=0o700)
    prodex.mkdir(mode=0o700)
    temporary.mkdir()
    workspace.mkdir()
    (prodex / "policy.toml").write_bytes(policy)
    for directory, event in ((prodex / "chosen", TOKEN_EVENT), (temporary, TMP_EVENT)):
        directory.mkdir(exist_ok=True)
        (directory / "prodex-runtime-fixture.log").write_bytes(event)
    command = sandbox_command(
        binary, root, ["log", "last", "--json"],
        argv0="prodex" if binary == ORACLE else "modex",
        environment={"PRODEX_HOME": str(prodex), "TMPDIR": str(temporary)},
    )
    result = subprocess.run(command, capture_output=True, timeout=20, check=False)
    return result.returncode, result.stdout, result.stderr


class PolicyLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_resource_and_structure_boundaries_match_oracle(self):
        cases = []
        prefix = 'version=1\n[runtime]\nlog_dir="chosen"\n'
        for depth in (79, 80, 81):
            cases.append((f"array-depth-{depth}", (prefix + f"[future]\nv={nested_array(depth)}\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"mixed-depth-{depth}", (prefix + f"[future]\nv={mixed_nested_value(depth)}\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"inline-depth-{depth}", (prefix + f"[future]\nv={nested_inline(depth)}\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"runtime-unknown-array-depth-{depth}", (prefix + f"unknown={nested_array(depth)}\n").encode(), 101 if depth <= 80 else 202))
            path = dotted_key(depth)
            cases.append((f"dotted-key-depth-{depth}", (prefix + f"{path}=1\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"header-depth-{depth}", (prefix + f"[{path}]\nv=1\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"array-table-depth-{depth}", (prefix + f"[[{path}]]\nv=1\n").encode(), 101 if depth <= 80 else 202))
            cases.append((f"dotted-in-header-depth-{depth}", (prefix + f"[future]\n{'.'.join(['child'] * depth)}=1\n").encode(), 101 if depth <= 80 else 202))

        for header_depth, key_depth in ((39, 40), (40, 40), (40, 41)):
            header = dotted_key(header_depth)
            key = ".".join(["child"] * key_depth)
            cases.append((f"header-plus-dotted-{header_depth}-{key_depth}", (prefix + f"[{header}]\n{key}=1\n").encode(), 101))

        for total_depth in (80, 81):
            child_path = ".".join(["child"] * (total_depth - 1))
            source = prefix + f"[[future]]\n[[future.{child_path}]]\nv=1\n"
            cases.append((f"array-table-super-depth-{total_depth}", source.encode(), 101 if total_depth == 80 else 202))

        cases.extend([
            ("quoted-dot-keys", (prefix + '["a.b.c"."d.e"]\nv=1\n').encode(), 101),
            ("inline-dotted-depth-80", (prefix + "[future]\nv={" + ".".join(["k"] * 80) + "=1}\n").encode(), 101),
            ("inline-dotted-depth-81", (prefix + "[future]\nv={" + ".".join(["k"] * 81) + "=1}\n").encode(), 202),
            ("inline-key-plus-nested-value", (prefix + "[future]\nv={" + ".".join(["k"] * 40) + "=" + nested_array(41) + "}\n").encode(), 101),
            ("dotted-key-plus-inline-value", (prefix + ".".join(["future"] * 40) + "=" + nested_inline(41) + "\n").encode(), 101),
            ("header-plus-nested-array", (prefix + f"[{dotted_key(40)}]\nv={nested_array(41)}\n").encode(), 101),
            ("quoted-dots-are-one-segment", (prefix + '["a.b.c.d.e"]\nv=1\n').encode(), 101),
            ("inline-dotted-40x80", (prefix + "[future]\nv=" + nested_dotted_inline(40, 80) + "\n").encode(), 101),
            ("inline-dotted-80x80", (prefix + "[future]\nv=" + nested_dotted_inline(80, 80) + "\n").encode(), 101),
            ("array-inline-dotted-40x80", (prefix + "[future]\nv=" + nested_dotted_inline(40, 80, arrays=True) + "\n").encode(), 101),
        ])

        long_key = "k" * 131072
        long_string = "s" * 262144
        cases.extend([
            ("long-key", f"version=1\n[runtime]\nlog_dir=\"chosen\"\n[future]\n{long_key}=1\n".encode(), 101),
            ("long-string", f"version=1\n[runtime]\nlog_dir=\"chosen\"\n[future]\nv=\"{long_string}\"\n".encode(), 101),
            ("escaped-multiline", b'version=1\n[runtime]\nlog_dir="chosen"\n[future]\nv="""start\\\n  ' + b'x' * 131072 + b'\\\n  end"""\n', 101),
            ("duplicate-key", b'version=1\n[runtime]\nlog_dir="chosen"\n[runtime]\nlog_dir="other"\n', 202),
            ("redefined-table", b'version=1\n[runtime]\nlog_dir="chosen"\n[runtime]\n', 202),
            ("malformed-tail", b'version=1\n[runtime]\nlog_dir="chosen"\n[future]\nv=1\nnot valid = [\n', 202),
        ])

        mismatches = []
        with tempfile.TemporaryDirectory(prefix="policy-limits-") as temporary:
            base = Path(temporary)
            for name, policy, expected in cases:
                with self.subTest(case=name):
                    case_base = base / name
                    case_base.mkdir()
                    baseline = run(ORACLE, policy, case_base, "oracle")
                    actual = run(MODEX, policy, case_base, "modex")
                    self.assertEqual(baseline[0], 0, (name, baseline[2]))
                    self.assertEqual(json.loads(baseline[1])["input_tokens"], expected, name)
                    self.assertEqual(actual[0], 0, (name, actual[2]))
                    self.assertEqual(json.loads(actual[1])["input_tokens"], expected, name)
                    if baseline != actual:
                        mismatches.append((name, policy, baseline, actual))
        if mismatches:
            details = []
            for name, policy, baseline, actual in mismatches:
                details.append(f"{name}: selected oracle={json.loads(baseline[1])['input_tokens']}, modex={json.loads(actual[1])['input_tokens']}")
            self.fail("policy boundary differences:\n" + "\n".join(details))


if __name__ == "__main__":
    unittest.main()
