"""Compare session help and argument errors with official-release fixtures."""

import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from session_oracle import fixture, sandbox_command
import test_cli
from test_cli import HISTORICAL_04391_ORACLE_SHA256, MODEX, ORACLE, ROOT
from capture_session_cli import map_executable


class SessionCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_release_help_and_argument_diagnostics(self):
        captured = json.loads((ROOT / "docs/evidence/baseline/session-cli.json").read_text())
        self.assertEqual(captured["oracle_sha256"], HISTORICAL_04391_ORACLE_SHA256)
        path_sensitive_cases = {
            ("session", "current", option, value)
            for option in ("--profile", "--query", "--cwd")
            for value in ("-", "+")
        }
        with tempfile.TemporaryDirectory(prefix="modex-session-cli-check-") as directory:
            for index, case in enumerate(captured["cases"]):
                with self.subTest(arguments=case["arguments"]):
                    if tuple(case["arguments"]) in path_sensitive_cases:
                        with tempfile.TemporaryDirectory(prefix="ms-", dir="/tmp") as path_directory:
                            for path_kind, path_name in (
                                ("short", f"{index}-short"),
                                ("long", f"{index}-" + "x" * 140),
                            ):
                                root = Path(path_directory) / path_name
                                root.mkdir()
                                (root / "home").mkdir(mode=0o700)
                                (root / "workspace").mkdir()
                                outputs = []
                                for name, binary in (("prodex", ORACLE), ("modex", MODEX)):
                                    result = subprocess.run(
                                        sandbox_command(binary, root, case["arguments"], argv0=name),
                                        capture_output=True, timeout=10, check=False)
                                    stdout = result.stdout.decode()
                                    stderr = result.stderr.decode()
                                    if path_kind == "short":
                                        stdout = stdout.replace(str(root), "<FIXTURE_ROOT>")
                                        stderr = stderr.replace(str(root), "<FIXTURE_ROOT>")
                                    if name == "modex":
                                        stdout = map_executable(stdout)
                                        stderr = map_executable(stderr)
                                    output = (result.returncode, stdout, stderr)
                                    outputs.append(output)
                                    if path_kind == "short":
                                        expected_stdout = case["stdout"] if name == "prodex" else map_executable(case["stdout"])
                                        expected_stderr = case["stderr"] if name == "prodex" else map_executable(case["stderr"])
                                        self.assertEqual(output, (case["exit_code"], expected_stdout, expected_stderr))
                                    if not case["new_paths"]:
                                        created = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                                                         if path not in (root / "home", root / "workspace"))
                                        self.assertEqual(created, [])
                                self.assertEqual(outputs[1], outputs[0])
                        continue
                    for name, binary in (("prodex", ORACLE), ("modex", MODEX)):
                        root = Path(directory) / f"{index}-{name}"
                        root.mkdir()
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir()
                        result = subprocess.run(sandbox_command(binary, root, case["arguments"], argv0=name),
                                                capture_output=True, timeout=10, check=False)
                        expected_stdout = case["stdout"] if name == "prodex" else map_executable(case["stdout"])
                        expected_stderr = case["stderr"] if name == "prodex" else map_executable(case["stderr"])
                        stdout = result.stdout.replace(str(root).encode(), b"<FIXTURE_ROOT>")
                        stderr = result.stderr.replace(str(root).encode(), b"<FIXTURE_ROOT>")
                        self.assertEqual((result.returncode, stdout, stderr),
                                         (case["exit_code"], expected_stdout.encode(), expected_stderr.encode()))
                        if not case["new_paths"]:
                            created = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                                             if path not in (root / "home", root / "workspace"))
                            self.assertEqual(created, [])

    def test_root_delimiter_errors_match_release_with_isolated_session_fixture(self):
        cases = [
            ["session", "--", "--help"],
            ["session", "--", "--json"],
            ["session", "--", "-h"],
            ["session", "--", "lits"],
            ["session", "--", "list"],
        ]
        with tempfile.TemporaryDirectory(prefix="modex-session-root-cli-check-") as directory:
            for index, arguments in enumerate(cases):
                with self.subTest(arguments=arguments):
                    outputs = []
                    for label, binary, argv0 in (("baseline", ORACLE, "prodex"),
                                                  ("modex", MODEX, "modex")):
                        root = Path(directory) / f"{index}-{label}"
                        root.mkdir()
                        fixture(root)
                        before = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                                  for path in root.rglob("*")}
                        result = subprocess.run(sandbox_command(binary, root, arguments, argv0=argv0),
                                                capture_output=True, timeout=10, check=False)
                        stdout = result.stdout.decode().replace(str(root), "<FIXTURE_ROOT>")
                        stderr = result.stderr.decode().replace(str(root), "<FIXTURE_ROOT>")
                        outputs.append((result.returncode, map_executable(stdout), map_executable(stderr)))
                        after = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                                 for path in root.rglob("*")}
                        self.assertEqual(after, before)
                    self.assertEqual(outputs[1], outputs[0])

    def test_generated_argument_sequences(self):
        generator = random.Random(439)
        choices = ["--json", "--id-only", "--resume-command", "--parent-only", "--include-subagents",
                   "--profile", "--query=alpha", "--limit", "--limit=1", "--limit=+", "--cwd=.",
                   "main", "bad", "--", "-", "-hh", "-xh", "--help=bad", "extra=foo"]
        cases = [["session", generator.choice(("list", "current")),
                  *generator.choices(choices, k=generator.randint(0, 5))] for _ in range(120)]
        for name in ("json", "id-only", "resume-command", "profile", "query", "limit", "cwd", "help"):
            for _ in range(4):
                index = generator.randrange(len(name))
                typo = name[:index] + generator.choice("abcdefxyz") + name[index + 1:]
                cases.append(["session", generator.choice(("list", "current")), "--" + typo])
        with tempfile.TemporaryDirectory(prefix="modex-cli-generated-") as directory:
            for index, arguments in enumerate(cases):
                with self.subTest(arguments=arguments):
                    outputs = []
                    for label, binary, argv0 in (("baseline", ORACLE, "prodex"), ("modex", MODEX, "modex")):
                        root = Path(directory) / f"{index}-{label}"
                        root.mkdir()
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir()
                        result = subprocess.run(sandbox_command(binary, root, arguments, argv0=argv0),
                                                capture_output=True, timeout=10, check=False)
                        stdout = result.stdout.decode().replace(str(root), "<FIXTURE_ROOT>")
                        stderr = result.stderr.decode().replace(str(root), "<FIXTURE_ROOT>")
                        outputs.append((result.returncode, map_executable(stdout), map_executable(stderr)))
                    self.assertEqual(outputs[1], outputs[0])


if __name__ == "__main__":
    unittest.main()
