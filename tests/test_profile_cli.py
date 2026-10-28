"""Compare stateless profile CLI routes with the frozen release."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli


PROFILE_COMMANDS = (
    "add", "export", "import", "import-current", "list", "remove", "use",
)


def run_isolated(binary, arguments, argv0):
    with tempfile.TemporaryDirectory(prefix="modex-profile-cli-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        workspace = root / "workspace"
        workspace.mkdir()
        result = subprocess.run(
            sandbox_command(binary, root, arguments, argv0=argv0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        paths = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path not in (home, workspace)
        )
        return result, paths


def map_executable(output, baseline_executable="prodex", executable="modex"):
    return output.replace(
        b"Usage: " + baseline_executable.encode() + b" ",
        b"Usage: " + executable.encode() + b" ",
    )


class ProfileCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_help_matches(self, arguments, baseline_argv0="prodex", executable="modex"):
        baseline, baseline_paths = run_isolated(test_cli.ORACLE, arguments, baseline_argv0)
        modex, modex_paths = run_isolated(test_cli.MODEX, arguments, executable)
        self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (0, map_executable(baseline.stdout, baseline_argv0, executable), b""),
        )
        self.assertEqual(baseline_paths, [])
        self.assertEqual(modex_paths, [])

    def assert_unimplemented_error_without_mutation(self, arguments):
        baseline, baseline_paths = run_isolated(test_cli.ORACLE, arguments, "prodex")
        modex, modex_paths = run_isolated(test_cli.MODEX, arguments, "modex")
        self.assertNotEqual(baseline.returncode, 0)
        self.assertEqual(baseline.stdout, b"")
        self.assertEqual(modex.returncode, 1)
        self.assertEqual(modex.stdout, b"")
        self.assertIn(b"has not implemented the requested command", modex.stderr)
        self.assertEqual(baseline_paths, [])
        self.assertEqual(modex_paths, [])

    def test_group_help_routes_match_without_home_mutation(self):
        for arguments in (
            ["profile", "--help"],
            ["profile", "-h"],
            ["help", "profile"],
            ["profile", "help"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_help_matches(arguments)

    def test_each_profile_subcommand_help_matches_without_home_mutation(self):
        for command in PROFILE_COMMANDS:
            for flag in ("-h", "--help"):
                with self.subTest(command=command, flag=flag):
                    self.assert_help_matches(["profile", command, flag])

    def test_first_help_flag_ignores_trailing_arguments(self):
        for flag in ("-h", "--help"):
            for tail in (["synthetic"], ["--bogus", "--", "synthetic"]):
                with self.subTest(command="profile", flag=flag, tail=tail):
                    self.assert_help_matches(["profile", flag, *tail])
                for command in PROFILE_COMMANDS:
                    with self.subTest(command=command, flag=flag, tail=tail):
                        self.assert_help_matches(["profile", command, flag, *tail])

    def test_profile_help_aliases_and_custom_executable_name(self):
        self.assert_help_matches(["profile", "list", "-h"])
        self.assert_help_matches(["help", "profile", "add"])
        self.assert_help_matches(["profile", "help", "use"])
        self.assert_help_matches(
            ["profile", "--help"], baseline_argv0="custom-prodex", executable="custom-modex"
        )

    def test_missing_profile_subcommand_matches_usage_error_without_mutation(self):
        baseline, baseline_paths = run_isolated(test_cli.ORACLE, ["profile"], "prodex")
        modex, modex_paths = run_isolated(test_cli.MODEX, ["profile"], "modex")
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (2, b"", map_executable(baseline.stderr)),
        )
        self.assertEqual(baseline_paths, [])
        self.assertEqual(modex_paths, [])

    def test_malformed_help_prefixes_do_not_become_successful_help(self):
        for arguments in (
            ["profile", "add", "--activate", "--activate", "--help"],
            ["profile", "add", "--codex-home", "/synthetic", "--codex-home", "/synthetic", "--help"],
            ["profile", "add", "--codex-home=", "--help"],
            ["profile", "add", "--bogus", "--help"],
            ["profile", "add", "-z", "--help"],
            ["profile", "list", "--bogus", "--help"],
            ["profile", "--bad", "--help"],
            ["profile", "help", "list", "--bogus"],
            ["help", "profile", "list", "--bogus"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_unimplemented_error_without_mutation(arguments)

    def test_valid_arguments_before_help_remain_mismatches(self):
        for arguments in (
            ["profile", "add", "synthetic-name", "--help"],
            ["profile", "add", "--activate", "--help"],
            ["profile", "export", "--no-password", "--help"],
            ["profile", "remove", "synthetic-name", "-h"],
            ["profile", "import-current", "synthetic-name", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_paths = run_isolated(test_cli.ORACLE, arguments, "prodex")
                modex, modex_paths = run_isolated(test_cli.MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertIn(b"Usage: prodex profile ", baseline.stdout)
                self.assertEqual((modex.returncode, modex.stdout), (1, b""))
                self.assertIn(b"has not implemented the requested command", modex.stderr)
                self.assertEqual((baseline_paths, modex_paths), ([], []))

    def test_unknown_profile_subcommands_remain_errors_without_mutation(self):
        for arguments in (
            ["profile", "wat"],
            ["profile", "wat", "--help"],
            ["profile", "lits"],
            ["profile", "help", "bogus"],
            ["help", "profile", "bogus"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_unimplemented_error_without_mutation(arguments)

    def test_profile_list_stays_unimplemented_instead_of_skipping_release_locks(self):
        baseline, baseline_paths = run_isolated(
            test_cli.ORACLE, ["profile", "list"], "prodex"
        )
        modex, modex_paths = run_isolated(test_cli.MODEX, ["profile", "list"], "modex")
        self.assertEqual(baseline.returncode, 0)
        self.assertIn(b"No profiles configured.", baseline.stdout)
        self.assertTrue(
            {
                "home/.prodex/profile-lifecycle.json.lock",
                "home/.prodex/runtime-housekeeping.lock",
                "home/.prodex/update-check.lock",
            }.issubset(baseline_paths)
        )
        self.assertEqual(modex.returncode, 1)
        self.assertIn(b"has not implemented the requested command", modex.stderr)
        self.assertEqual(modex_paths, [])


if __name__ == "__main__":
    unittest.main()
