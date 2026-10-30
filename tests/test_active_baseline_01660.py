"""Process checks against the official 0.166.0 active release."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


def isolated_super_cli(binary, arguments, argv0):
    from session_oracle import sandbox_command

    with tempfile.TemporaryDirectory(prefix="modex-active-super-cli-") as temporary:
        root = Path(temporary)
        home = root / "home"
        workspace = root / "workspace"
        home.mkdir(mode=0o700)
        workspace.mkdir()
        command = sandbox_command(binary, root, arguments, argv0=argv0)
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
        )
        created = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path not in (home, workspace)
        )
        return result, created


def normalize_super_cli_executable(output):
    output = output.replace(b"Usage: prodex ", b"Usage: modex ")
    for command in (b"super", b"run", b"doctor", b"login"):
        output = output.replace(b"prodex " + command, b"modex " + command)
    return output


class ActiveBaseline01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_version_identity_without_state_changes(self):
        for binary, expected in ((ORACLE, b"prodex 0.166.0\n"), (MODEX, b"modex 0.1.0-dev\n")):
            for flag in ("--version", "-V"):
                with self.subTest(binary=str(binary), flag=flag), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    home = root / "home"
                    home.mkdir(mode=0o700)
                    result = subprocess.run(
                        [str(binary), flag], cwd=root, stdin=subprocess.DEVNULL,
                        env={"HOME": str(home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1"},
                        capture_output=True, timeout=10, check=False,
                    )
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b""))
                    self.assertEqual(list(home.iterdir()), [])
                    self.assertEqual(sorted(path.name for path in root.iterdir()), ["home"])

    def test_super_hook_initialize_uses_active_identity(self):
        from test_super_launch import SuperLaunchTests

        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                result, records, upstream, state = SuperLaunchTests().run_launch(
                    binary=binary, scenario="buffered",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(upstream), 1)
                self.assertEqual(state["leftovers"], [])
                identity = [record["params"]["clientInfo"] for record in records
                            if record.get("kind") == "request" and record.get("method") == "initialize"]
                self.assertEqual(identity, [{"name": "prodex-hook-trust", "version": "0.166.0"}])

    def test_log_last_matches_synthetic_transcript_and_runtime_events(self):
        from test_logs import session_fixture

        sentinel = "synthetic-secret-token"
        records = [
            {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": {
                "request": "7", "transport": "http", "route": "responses", "profile": "main",
                "bytes": "10", "logged_bytes": "10", "truncated": "false",
                "payload_b64": base64.b64encode(b'{"input":"hello"}').decode()}},
            {"timestamp": "2026-10-24T01:02:05Z", "event": "token_usage", "fields": {
                "request": "7", "transport": "http", "profile": "main", "source": "responses",
                "input_tokens": "12", "cached_input_tokens": "3", "output_tokens": "4",
                "reasoning_tokens": "1"}},
        ]
        outputs = []
        app_state_paths = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-active-log-last-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                runtime = root / "runtime"
                runtime.mkdir()
                (runtime / "prodex-runtime-fixture.log").write_text(
                    "\n".join(map(json.dumps, records)) + "\n")
                session_fixture(root, "Authorization: Bearer " + sentinel)
                session_path = next((root / "home/.codex").rglob("*.jsonl"))
                before = session_path.read_bytes()
                result = subprocess.run(
                    sandbox_command(
                        binary, root, ["log", "last", "--json"],
                        argv0="prodex" if binary == ORACLE else "modex",
                        environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(runtime)},
                    ),
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertNotIn(sentinel.encode(), result.stdout)
                self.assertEqual(session_path.read_bytes(), before)
                app_root = root / "home/.prodex"
                app_state_paths.append(sorted(
                    [str(app_root.relative_to(root)), *(
                        str(path.relative_to(root)) for path in app_root.rglob("*")
                    )]
                ))
                outputs.append(result.stdout)

        self.assertEqual(outputs[1], outputs[0])
        self.assertEqual(app_state_paths, [["home/.prodex"], ["home/.prodex"]])
        events = [json.loads(line) for line in outputs[0].splitlines()]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["source"], "user")
        self.assertEqual(events[1]["route"], "responses")
        self.assertEqual(events[1]["payload"], '{"input":"hello"}')
        self.assertEqual(events[2]["event"], "token_usage")
        self.assertEqual(events[2]["input_tokens"], 12)

    def test_super_help_and_selected_parser_cases_match_active_release(self):
        cases = (
            ("help", ("super", "--help"), 0),
            ("missing profile value", ("super", "--profile"), 2),
            ("invalid provider", ("super", "--provider", "synthetic-invalid"), 2),
            ("negative context window", ("super", "--context-window", "-1"), 2),
            ("zero context window before help", ("super", "--context-window", "0", "--help"), 0),
        )
        for label, arguments, expected_status in cases:
            with self.subTest(case=label):
                baseline, baseline_created = isolated_super_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, modex.returncode), (expected_status, expected_status))
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (normalize_super_cli_executable(baseline.stdout),
                     normalize_super_cli_executable(baseline.stderr)),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_super_validated_option_values_match_active_release(self):
        cases = (
            ("base URL before help", ("super", "--base-url", "ftp://synthetic.invalid", "--help"), 0),
            ("provider URL before help", ("super", "--url", "ftp://synthetic.invalid", "--help"), 0),
            ("sub-agent URL", ("super", "--sub-agent-url", "ftp://synthetic.invalid", "--help"), 2),
            ("optional tool", ("super", "--tool", "synthetic-unknown", "--help"), 2),
            ("required tool", ("super", "--require-tool", "synthetic-unknown", "--help"), 2),
            ("tool alias", ("super", "--tool", " RTK ", "--help"), 0),
            ("required tool alias", ("super", "--require-tool", " CBM ", "--help"), 0),
        )
        for label, arguments, expected_status in cases:
            with self.subTest(case=label):
                baseline, baseline_created = isolated_super_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, modex.returncode), (expected_status, expected_status))
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (normalize_super_cli_executable(baseline.stdout),
                     normalize_super_cli_executable(baseline.stderr)),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_super_runtime_url_validation_stays_before_startup(self):
        invalid = "ftp://synthetic.invalid"
        valid = "http://127.0.0.1:8131"
        cases = (
            (("super", "--url", invalid), 1, b"Error: invalid --url:"),
            (("super", "exec", "--url", invalid), 1, b"Error: invalid --url:"),
            (("super", "--base-url", invalid), 1, b"Error: invalid --base-url:"),
            (("super", "exec", "--base-url", invalid), 1, b"Error: invalid --base-url:"),
            (("super", "--url", valid, "--url", invalid), 2, b"cannot be used multiple times"),
            (("super", "exec", "--url", valid, "--url", invalid), 1, b"Error: invalid --url:"),
        )
        for arguments, expected_status, diagnostic in cases:
            with self.subTest(arguments=arguments):
                modex, created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual(modex.returncode, expected_status)
                self.assertEqual(modex.stdout, b"")
                self.assertIn(diagnostic, modex.stderr)
                self.assertEqual(created, [])

    def test_doctor_help_matches_active_release_without_state_changes(self):
        cases = (
            (("doctor", "--help"), 0),
            (("doctor", "-h"), 0),
            (("doctor", "--quota", "--help"), 0),
            (("doctor", "--tail-bytes", "12", "--help"), 0),
            (("doctor", "--tail-bytes=12", "--help"), 0),
            (("doctor", "--bundle", "--help"), 0),
            (("doctor", "--bundle=path", "--help"), 0),
            (("doctor", "--bundle", "path", "--help"), 0),
            (("doctor", "--bundle=--help", "--help"), 0),
            (("doctor", "--help", "--bogus"), 0),
            (("doctor", "--bogus", "--help"), 2),
            (("doctor", "--tail-bytes=bogus", "--help"), 2),
            (("doctor", "--tail-bytes", "bogus", "--help"), 2),
            (("doctor", "--tail-bytes", "--help"), 2),
            (("doctor", "--tail-bytes=--help"), 2),
            (("doctor", "--tail-bytes", "--", "--help"), 2),
            (("doctor", "--bundle", "-", "--help"), 0),
            (("doctor", "--bundle=", "--help"), 2),
            (("doctor", "--bundle", "", "--help"), 2),
            (("doctor", "--quota", "--quota", "--help"), 2),
            (("doctor", "--tail-bytes", "12", "--tail-bytes", "13", "--help"), 2),
            (("doctor", "--bundle", "one", "--bundle", "two", "--help"), 2),
            (("doctor", "--quota=yes", "--help"), 2),
            (("doctor", "--", "--help"), 2),
            (("doctor", "--", "--quota", "--help"), 2),
            (("doctor", "--quota", "--", "--help"), 2),
        )
        for arguments, expected_status in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_super_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, modex.returncode), (expected_status, expected_status))
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (normalize_super_cli_executable(baseline.stdout),
                     normalize_super_cli_executable(baseline.stderr)),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_doctor_invalid_arguments_match_release_without_help(self):
        cases = (
            ("--json",),
            ("--suggest-policy",),
            ("--bundle",),
            ("--redacted",),
            ("--json", "--redacted"),
            ("--runtime", "--json", "--bundle"),
            ("--tail-bytes",),
            ("--tail-bytes=bogus",),
            ("--bundle=",),
            ("--bundle", ""),
        )
        for options in cases:
            arguments = ("doctor", *options)
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_super_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, modex.returncode), (2, 2))
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (normalize_super_cli_executable(baseline.stdout),
                     normalize_super_cli_executable(baseline.stderr)),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_doctor_execution_stays_guarded_without_help(self):
        for arguments in (
            ("doctor",),
            ("doctor", "--quota"),
            ("doctor", "--runtime", "--json"),
        ):
            with self.subTest(arguments=arguments):
                modex, created = isolated_super_cli(MODEX, arguments, "modex")
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])

    def test_exec_model_help_records_the_guarded_runtime_boundary(self):
        # An empty HOME, cleared sandbox environment, and isolated network keep this probe offline.
        arguments = ("super", "exec", "--model", "--help")
        baseline, baseline_created = isolated_super_cli(ORACLE, arguments, "prodex")
        modex, modex_created = isolated_super_cli(MODEX, arguments, "modex")

        self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
        self.assertIn(b"no active profile selected", baseline.stderr)
        self.assertEqual((modex.returncode, modex.stdout), (1, b""))
        self.assertIn(b"Super startup is not implemented", modex.stderr)
        self.assertEqual(baseline_created, [
            "home/.prodex",
            "home/.prodex/profile-lifecycle.json.lock",
            "home/.prodex/runtime-housekeeping.last-run",
            "home/.prodex/runtime-housekeeping.lock",
            "home/.prodex/update-check.lock",
        ])
        self.assertEqual(modex_created, [])


    def test_custom_tool_input_matches_active_provider_request_shape(self):
        from test_deepseek_continuation import buffered_reply, observe_turns

        missing = object()
        custom_values = [
            ("object", {"query": "synthetic"}, '{"query":"synthetic"}', {}),
            ("nested-object", {"z": 1, "a": 2, "nested": {"z": 1, "a": 2}},
             '{"a":2,"nested":{"a":2,"z":1},"z":1}', {}),
            ("missing", missing, "", {}),
            ("null", None, "null", {}),
            ("string", "raw patch", "raw patch", {}),
            ("array", [1, "雪"], '[1,"雪"]', {}),
            ("number", 7, "7", {}),
            ("boolean", False, "false", {}),
            ("unicode-escaping", 'café 🌋 "quote"\nline\\tail',
             'café 🌋 "quote"\nline\\tail', {}),
            ("input-precedence", "input wins", "input wins", {
                "arguments": {"selected": "top-level"},
                "function": {"arguments": {"selected": "nested"}},
            }),
        ]
        paths = [("native", {}), ("fallback", {"safety_identifier": "synthetic-user"})]
        turns = []
        expected_custom_inputs = []
        for path_name, request_fields in paths:
            for name, item_input, expected_input, extra_fields in custom_values:
                call_id = "call_" + path_name + "_" + name
                item = {"type": "custom_tool_call", "call_id": call_id, "name": "apply_patch", **extra_fields}
                if item_input is not missing:
                    item["input"] = item_input
                output = {"type": "custom_tool_call_output", "call_id": call_id, "output": "synthetic result"}
                turns.append({"model": "deepseek-chat", "input": [item, output], **request_fields})
                expected_custom_inputs.append(expected_input)
        expected_function_arguments = []
        for path_name, request_fields in paths:
            call_id = "call_" + path_name + "_function_precedence"
            item = {
                "type": "function_call", "call_id": call_id, "name": "lookup",
                "input": {"selected": "input"}, "arguments": {"selected": "arguments"},
                "function": {"arguments": {"selected": "nested"}},
            }
            output = {"type": "function_call_output", "call_id": call_id, "output": "synthetic result"}
            turns.append({"model": "deepseek-chat", "input": [item, output], **request_fields})
            expected_function_arguments.append({"selected": "arguments"})
        observed = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [buffered_reply(index) for index in range(len(turns))],
                )
                self.assertEqual([row["status"] for row in responses], [200] * len(turns))
                self.assertEqual(len(upstream), len(turns))
                bodies = [json.loads(row["body"]) for row in upstream]
                calls = [body["messages"][0]["tool_calls"][0] for body in bodies]
                arguments = [json.loads(call["function"]["arguments"]) for call in calls]
                self.assertEqual([item["input"] for item in arguments[:len(expected_custom_inputs)]],
                                 expected_custom_inputs)
                self.assertEqual(arguments[len(expected_custom_inputs):], expected_function_arguments)
                observed.append(bodies)
        self.assertEqual(*observed)


if __name__ == "__main__":
    unittest.main()
