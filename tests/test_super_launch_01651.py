"""Active 0.165.1 reference checks for the production Codex probes."""

import hashlib
import os
from pathlib import Path
import unittest

import test_cli_01651 as active_cli
import test_super_launch as launch_support

ORACLE_04392 = Path(os.environ.get("PRODEX_ORACLE_04392", str(launch_support.ORACLE)))

PROBE_ENVIRONMENT = (
    "CODEX_HOME",
    "TEST_CODEX_LOG",
    "TEST_CODEX_LOG_APPEND",
    "TEST_CODEX_ARGS_LOG",
    "TEST_CODEX_ARGS_LOG_APPEND",
    "TEST_CODEX_STDIN_LOG",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_KEYS",
    "PRODEX_RUNTIME_LOCAL_KEYS_JSON",
)
NATIVE_CODEX = launch_support.MODEX.parent / "tests/codex_argv_child"
SENTINEL_ENVIRONMENT = {
    name: (
        '["synthetic-probe-sentinel-runtime-key"]'
        if name == "PRODEX_RUNTIME_LOCAL_KEYS_JSON"
        else f"synthetic-probe-sentinel-{name.lower()}"
    )
    for name in PROBE_ENVIRONMENT
}


class ActiveSuperLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not active_cli.ORACLE.is_file() or hashlib.sha256(active_cli.ORACLE.read_bytes()).hexdigest() != active_cli.ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")
        if not ORACLE_04392.is_file() or hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != launch_support.ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.439.2 Linux release")
        if not launch_support.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not NATIVE_CODEX.is_file() or NATIVE_CODEX.stat().st_mode & 0o111 == 0:
            raise AssertionError("Build the native Codex fixture with make unit-build")

    def test_supported_exec_flags_match_01651(self):
        launch_support.check_safe_exec_flags(self, active_cli.ORACLE)

    def test_missing_exec_values_reach_child_for_both_releases(self):
        for arguments in (("exec", "--add-dir"), ("exec", "--enable"),
                          ("exec", "--disable"),
                          ("exec", "--add-dir", "--json", "synthetic prompt"),
                          ("exec", "--enable", "--json", "synthetic prompt")):
            captures = []
            for binary in (active_cli.ORACLE, ORACLE_04392, launch_support.MODEX):
                with self.subTest(arguments=arguments, binary=str(binary)):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary, scenario="exit-seven", codex_arguments=arguments,
                    )
                    self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    launch = next(record for record in records if record["kind"] == "launch")
                    captures.append(launch_support.normalized_app_server_args(launch["args"]))
            self.assertEqual(captures[0], captures[1])
            self.assertEqual(captures[0], captures[2])

    def test_repeat_launch_with_shared_history_documents_current_gap(self):
        for label, binary in (("0.165.1", active_cli.ORACLE), ("0.439.2", ORACLE_04392), ("Modex", launch_support.MODEX)):
            with self.subTest(binary=label):
                first, records, upstream, state = launch_support.run_private_launch(
                    binary, scenario="exit-seven", repeat_launch=True,
                )
                self.assertEqual(first.returncode, 7, first.stderr)
                self.assertEqual(state["repeat"].returncode, 1 if label == "Modex" else 7, state["repeat"].stderr)
                self.assertEqual(sum(record["kind"] == "launch" for record in records), 1 if label == "Modex" else 2)
                self.assertEqual(upstream, [])
                self.assertEqual(state["session"], '{"synthetic":true}\n')
                self.assertIn('{"synthetic":"preserve history"}\n', state["history"])
                self.assertEqual(state["leftovers"], [])
                if label == "Modex":
                    self.assertIn(b"cannot reconcile existing Codex data", state["repeat"].stderr)

    def test_explicit_full_access_matches_01651(self):
        launch_support.check_explicit_full_access(self, active_cli.ORACLE)

    def test_no_proxy_matches_01651(self):
        launch_support.check_no_proxy(self, active_cli.ORACLE)

    def test_probe_failure_and_environment_match_01651(self):
        outputs = []
        for binary in (active_cli.ORACLE, launch_support.MODEX):
            with self.subTest(binary=binary.name):
                result, records, upstream, state = launch_support.run_private_launch(
                    binary,
                    scenario="app-server-help-failure",
                    environment_overrides=SENTINEL_ENVIRONMENT,
                )
                self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                self.assertEqual([record["kind"] for record in records], ["probe", "probe"])
                probes = [record for record in records if record["kind"] == "probe"]
                self.assertEqual([record["args"] for record in probes], [
                    ["--version"], ["app-server", "--help"],
                ])
                self.assertEqual([record["kind"] for record in records], ["probe", "probe"])
                expected_environment = {name: None for name in PROBE_ENVIRONMENT}
                if binary == active_cli.ORACLE:
                    expected_environment.update({
                        name: SENTINEL_ENVIRONMENT[name]
                        for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", "PRODEX_RUNTIME_LOCAL_KEYS_JSON")
                    })
                self.assertEqual([record["environment"] for record in probes], [expected_environment] * 2)
                self.assertEqual((upstream, state["leftovers"]), ([], []))
                self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                self.assertNotIn(b"synthetic-probe-sentinel", result.stdout + result.stderr)
                outputs.append((
                    result.returncode,
                    result.stdout,
                    launch_support.normalized_codex_path(result.stderr),
                ))

        expected = (
            b"Error: Codex app-server capability probe failed for <CODEX> with status 7. "
            b"Install or update the official Codex CLI with `npm install -g @openai/codex@latest` "
            b"(https://developers.openai.com/codex/cli), verify `codex --version`, or set "
            b"PRODEX_CODEX_BIN to its executable path. Prodex accepts compatible Codex releases "
            b"at or above its minimum capability baseline; the latest stable release is recommended."
        )
        self.assertEqual(outputs[0], outputs[1])
        self.assertTrue(outputs[0][2].endswith(expected + b"\n"))

    def test_deepseek_provider_panel_key_counts_match_both_releases(self):
        cases = (
            (
                "single",
                "synthetic-single-provider-key",
                {},
                "Using provider 'deepseek' through the local compatibility proxy. Smart Context rewrites require a proven tokenizer. Using one provider API key; API-key rotation is skipped and quota preflight stays disabled.",
            ),
            (
                "multiple",
                None,
                {"DEEPSEEK_API_KEYS": "synthetic-rotation-key-a,synthetic-rotation-key-b"},
                "Using provider 'deepseek' through the local compatibility proxy. Smart Context rewrites require a proven tokenizer. API-key rotation is enabled across 2 keys; quota preflight stays disabled.",
            ),
        )
        binaries = (active_cli.ORACLE, ORACLE_04392, launch_support.MODEX)
        for label, api_key, environment, expected_panel in cases:
            with self.subTest(key_count=label):
                panels = []
                for binary in binaries:
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary,
                        scenario="app-server-help-failure",
                        api_key=api_key,
                        environment_overrides=environment,
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                    self.assertEqual([record["args"] for record in records if record["kind"] == "probe"], [
                        ["--version"], ["app-server", "--help"],
                    ])
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    output = result.stdout + result.stderr
                    self.assertNotIn(b"synthetic-provider-key", output)
                    self.assertNotIn(b"synthetic-single-provider-key", output)
                    for secret in environment.values():
                        for key in secret.split(","):
                            self.assertNotIn(key.encode(), output)
                    text = result.stderr.decode("utf-8")
                    start = text.index("[ Runtime Provider ]")
                    end = text.index("Error: Codex app-server capability probe failed", start)
                    panel_lines = text[start:end].splitlines()[1:]
                    panels.append(" ".join(line.strip() for line in panel_lines))
                self.assertEqual(panels, [expected_panel] * len(binaries))

    def test_missing_explicit_profile_matches_both_releases(self):
        progress = (
            b"Prodex launch: preparing runtime launch...\n"
            b"Prodex launch: Smart Context runtime proxy requested.\n"
            b"Prodex launch: local provider bridge requested.\n"
        )
        cases = (
            ("main", progress + b"Error: profile 'main' does not exist\n"),
            ("", progress + b"Error: profile '' does not exist\n"),
        )
        binaries = (active_cli.ORACLE, ORACLE_04392, launch_support.MODEX)
        results = {}
        for profile, expected_stderr in cases:
            for binary in binaries:
                with self.subTest(profile=profile, binary=binary.name):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary,
                        scenario="exit-seven",
                        super_arguments=("--profile", profile),
                    )
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b"", expected_stderr))
                    self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))
                    self.assertIsNone(state["session"])
                    self.assertEqual(state["extra"], [])
                    self.assertIsNone(state["config"])
                    results[(profile, binary)] = state["managed"]

        for profile, _ in cases:
            for oracle in (active_cli.ORACLE, ORACLE_04392):
                self.assertIn("state/profile-lifecycle.json.lock", results[(profile, oracle)])
            self.assertNotIn("state/profile-lifecycle.json.lock", results[(profile, launch_support.MODEX)])

    def test_codex_binary_selection_reaches_probes_and_child_launch(self):
        for mode in ("relative", "symlink", "command", "path", "relative-path", "path-skips-wrapper"):
            with self.subTest(mode=mode):
                outputs = []
                states = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary=binary,
                        scenario="exit-seven",
                        codex_mode=mode,
                        environment_overrides={"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.2"},
                    )
                    self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertNotIn(b"synthetic-codex-key", result.stdout + result.stderr)
                    self.assertEqual(
                        [record["args"] for record in records if record["kind"] == "probe"],
                        [["--version"], ["app-server", "--help"]],
                    )
                    launch = next(record for record in records if record["kind"] == "launch")
                    trace = [
                        (
                            record["kind"],
                            launch_support.normalized_app_server_args(record["args"])
                            if "args" in record else None,
                            record.get("method"),
                            record.get("environment"),
                        )
                        for record in records
                    ]
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                        trace,
                    ))
                    states.append(state)
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(
                    tuple(states[0][name] for name in ("leftovers", "session", "extra", "config")),
                    tuple(states[1][name] for name in ("leftovers", "session", "extra", "config")),
                )
                self.assertIn("shared/sessions/.prodex-maintenance.lock", states[0]["managed"])
                self.assertNotIn("shared/sessions/.prodex-maintenance.lock", states[1]["managed"])

    def test_native_codex_argv0_matches_01651_for_probe_and_child_roles(self):
        canonical = str(NATIVE_CODEX.resolve())
        cases = (
            ("relative", "../codex"),
            ("symlink", "../codex-alias"),
            ("command", "codex"),
            ("command-cwd", "codex"),
            ("command-relative-path", "codex"),
            ("path", canonical),
            ("relative-path", canonical),
            ("path-skips-wrapper", canonical),
        )
        expected_args = [["--version"], ["app-server", "--help"]]
        for mode, requested_argv0 in cases:
            with self.subTest(mode=mode):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary=binary,
                        scenario="exit-seven",
                        codex_mode=mode,
                        codex_binary=NATIVE_CODEX,
                    )
                    self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                    self.assertEqual([record["args"] for record in records[:2]], expected_args)
                    self.assertIn("app-server", records[2]["args"])
                    self.assertIn("--stdio", records[2]["args"])
                    self.assertIn("exec", records[3]["args"])
                    trace = [(record["kind"], record["argv0"]) for record in records]
                    self.assertEqual(trace, [
                        ("probe", canonical),
                        ("probe", canonical),
                        ("preflight", requested_argv0),
                        ("launch", requested_argv0),
                    ])
                    outputs.append(trace)
                self.assertEqual(outputs[0], outputs[1])

    def test_shebang_codex_interpreter_path_matches_01651(self):
        cases = (
            ("relative", "../codex"),
            ("symlink", "../codex-alias"),
            ("command", None),
            ("command-cwd", "codex"),
            ("command-relative-path", "bin/codex"),
        )
        for mode, selected_script_path in cases:
            with self.subTest(mode=mode):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary=binary,
                        scenario="exit-seven",
                        codex_mode=mode,
                    )
                    self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    trace = [
                        (record["kind"], record["script_argv0"])
                        for record in records
                        if record["kind"] in ("probe", "preflight", "launch")
                    ]
                    canonical = records[0]["script_argv0"]
                    self.assertTrue(canonical.startswith("/"), canonical)
                    self.assertTrue(canonical.endswith("/codex"), canonical)
                    expected_child_path = selected_script_path or canonical.rsplit("/", 1)[0] + "/work/bin/codex"
                    self.assertEqual(trace, [
                        ("probe", canonical),
                        ("probe", canonical),
                        ("preflight", expected_child_path),
                        ("launch", expected_child_path),
                    ])
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                    ))
                self.assertEqual(outputs[0], outputs[1])

    def test_missing_codex_path_matches_01651_without_startup_side_effects(self):
        outputs = []
        states = []
        for binary in (active_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                binary=binary, scenario="exit-seven", codex_mode="missing"
            )
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))
            self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
            outputs.append((
                result.returncode,
                result.stdout,
                launch_support.normalized_codex_path(result.stderr),
            ))
            states.append(state)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(
            tuple(states[0][name] for name in ("leftovers", "session", "extra", "config")),
            tuple(states[1][name] for name in ("leftovers", "session", "extra", "config")),
        )
        self.assertIn("state/profile-lifecycle.json.lock", states[0]["managed"])
        self.assertNotIn("state/profile-lifecycle.json.lock", states[1]["managed"])
        self.assertTrue(outputs[0][2].endswith(
            b"Error: Codex CLI is unavailable. Install or update the official Codex CLI with "
            b"`npm install -g @openai/codex@latest` (https://developers.openai.com/codex/cli), "
            b"verify `codex --version`, or set PRODEX_CODEX_BIN to its executable path. Prodex "
            b"accepts compatible Codex releases at or above its minimum capability baseline; "
            b"the latest stable release is recommended.\n"
        ))

    def test_ci_progress_fallback_matches_01651_on_tty(self):
        outputs = []
        for binary in (active_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                binary=binary,
                scenario="exit-seven",
                environment_overrides={
                    "CODEX_CI": "1",
                    "MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1",
                },
                stderr_tty=True,
            )
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual([record["args"] for record in records if record["kind"] == "probe"], [["--version"]])
            self.assertEqual((upstream, state["leftovers"]), ([], []))
            self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
            self.assertNotIn(b"\x1b[", result.stderr)
            outputs.append((
                result.returncode,
                result.stdout,
                launch_support.normalized_codex_path(result.stderr),
            ))
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn(b"Prodex launch: preparing runtime launch...\r\n", outputs[0][2])

    def test_redirected_provider_panel_width_matches_01651(self):
        for columns in ("50", "120"):
            with self.subTest(columns=columns):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary,
                        scenario="app-server-help-failure",
                        environment_overrides={"PRODEX_TERM_COLUMNS": columns},
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                    self.assertEqual([record["kind"] for record in records], ["probe", "probe"])
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                    ))
                self.assertEqual(outputs[0], outputs[1])
                self.assertIn(b"[ Runtime Provider ]", outputs[0][2])
                self.assertIn(b"compatibility proxy.", outputs[0][2])

    def test_tty_fallback_progress_matches_01651(self):
        cases = (
            {"TERM": "dumb"},
            {"TERM": "xterm-256color", "PRODEX_TUI_STRICT": "true"},
        )
        for environment in cases:
            with self.subTest(environment=environment):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary=binary,
                        scenario="exit-seven",
                        environment_overrides={
                            **environment,
                            "MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1",
                        },
                        stderr_tty=True,
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                    self.assertEqual([record["args"] for record in records if record["kind"] == "probe"], [["--version"]])
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertNotIn(b"\x1b[", result.stderr)
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                    ))
                self.assertEqual(outputs[0], outputs[1])
                self.assertIn(b"[ Prodex Launch ]", outputs[0][2])
                self.assertIn(b"[ Runtime Provider ]", outputs[0][2])

    def test_minimum_codex_version_matches_01651(self):
        cases = (
            ({"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1"}, False),
            ({"MODEX_TEST_CODEX_VERSION": "codex 0.+153.2"}, True),
            ({"MODEX_TEST_CODEX_VERSION": "codex 0.153.+2"}, True),
            ({
                "MODEX_TEST_CODEX_VERSION": "Codex CLI 0.153.2!",
                "MODEX_TEST_CODEX_VERSION_STDERR": "1",
            }, True),
        )
        for environment, accepted in cases:
            with self.subTest(environment=environment):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary,
                        scenario="exit-seven",
                        environment_overrides=environment,
                    )
                    probes = [record["args"] for record in records if record["kind"] == "probe"]
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertNotIn(b"synthetic-probe-sentinel", result.stdout + result.stderr)
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                    ))
                    if accepted:
                        self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                        self.assertEqual(probes, [["--version"], ["app-server", "--help"]])
                        self.assertEqual(
                            [record["kind"] for record in records],
                            ["probe", "probe", "preflight", "request", "request", "request", "launch"],
                        )
                    else:
                        self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                        self.assertEqual(probes, [["--version"]])
                        self.assertEqual([record["kind"] for record in records], ["probe"])
                        self.assertIn(b"requires 0.153.2 or newer", result.stderr)
                self.assertEqual(outputs[0], outputs[1])

    def test_nonzero_version_probe_matches_01651(self):
        outputs = []
        for binary in (active_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.run_private_launch(
                binary,
                scenario="exit-seven",
                environment_overrides={"MODEX_TEST_CODEX_VERSION_EXIT": "7"},
            )
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual([record["kind"] for record in records], ["probe"])
            self.assertEqual(records[0]["args"], ["--version"])
            self.assertEqual((upstream, state["leftovers"]), ([], []))
            self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
            outputs.append((
                result.returncode,
                result.stdout,
                launch_support.normalized_codex_path(result.stderr),
            ))
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn(b"Codex version probe failed for <CODEX> with status 7.", outputs[0][2])

    def test_oversized_probe_capture_matches_01651(self):
        cases = (
            ({"MODEX_TEST_CODEX_VERSION_OVERSIZE": "1"}, [["--version"]], "Codex version probe"),
            ({"MODEX_TEST_CODEX_HELP_OVERSIZE": "1"},
             [["--version"], ["app-server", "--help"]], "Codex app-server capability probe"),
        )
        for environment, expected_probes, label in cases:
            with self.subTest(environment=environment):
                outputs = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary,
                        scenario="exit-seven",
                        environment_overrides=environment,
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                    self.assertEqual(
                        [record["args"] for record in records if record["kind"] == "probe"],
                        expected_probes,
                    )
                    self.assertEqual(
                        [record["kind"] for record in records],
                        ["probe"] * len(expected_probes),
                    )
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        launch_support.normalized_codex_path(result.stderr),
                    ))
                expected = (
                    b"Error: failed to probe Codex CLI at <CODEX>: "
                    + label.encode()
                    + b" output exceeded the limit"
                )
                self.assertEqual(outputs[0], outputs[1])
                self.assertTrue(outputs[0][2].endswith(expected + b"\n"))
