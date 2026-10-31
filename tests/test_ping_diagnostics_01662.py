"""Compare offline ping group diagnostics with the 0.166.2 release."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run, map_executable


class PingDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_missing_and_invalid_commands_match_without_mutation(self):
        for arguments in (("ping",), ("ping", "--"), ("ping", "--bogus"),
                          ("ping", "--bogus=value"), ("ping", "-xyz"), ("ping", "nope"),
                          ("ping", "banana"), ("ping", "opena"), ("ping", "-"),
                          ("ping", "--h"), ("ping", "--h=value"), ("ping", "--he"),
                          ("ping", "--hel"), ("ping", "--hlp"), ("ping", "--z"),
                          ("ping", "--o"),
                          ("ping", "--", "bogus"), ("ping", "--", "--help")):
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, list(arguments), "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, list(arguments), "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_unknown_arguments_match_without_mutation(self):
        for tail in (("--bogus",), ("--bogus=value",), ("-xyz",), ("unexpected",),
                     ("--bogus", "--help"), ("--", "unexpected"),
                     ("--", "--foo=x"), ("--", "--json"),
                     ("--h",), ("--h=value",), ("--he",), ("--hel",),
                     ("--hlp",), ("--jso",), ("--no-prox",), ("--z",)):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))

    def test_help_suggestion_follows_accepted_option_and_precedes_model_validation(self):
        for tail in (("--json", "--h"), ("--profile", "synthetic", "--he"),
                     ("--json", "--profile", "synthetic", "--hlp"),
                     ("--model", "", "--hlp")):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-help-near-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-help-near-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_missing_option_values_match_without_mutation(self):
        for tail in (("--profile",), ("-p",), ("--model",), ("--effort",),
                     ("--base-url",), ("--profile", "--json")):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_duplicate_options_match_without_mutation(self):
        cases = (
            ("--profile", "x", "-p", "y"),
            ("--profile=x", "--profile=y"),
            ("--model", "x", "--model", "y"),
            ("--effort=low", "--effort=high"),
            ("--base-url=x", "--base-url=y"),
            ("--no-proxy", "--no-proxy"),
            ("--json", "--json"),
        )
        for tail in cases:
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_empty_whitespace_and_control_models_match_release(self):
        expected = (1, b"", b"Error: --model must be nonempty and contain no control characters\n")
        invalid_values = (
            ("empty separated", ("--model", "")),
            ("empty attached", ("--model=",)),
            ("space only", ("--model", " ")),
            ("unicode whitespace only", ("--model", "\u2000\u00a0")),
            ("attached whitespace only", ("--model= \u2028",)),
            ("tab", ("--model", "\t")),
            ("embedded newline", ("--model=gpt-4\nmini",)),
            ("C0", ("--model", "\x1f")),
            ("DEL", ("--model", "\x7f")),
            ("C1 minimum", ("--model", "\u0080")),
            ("C1 NEL", ("--model", "\u0085")),
            ("C1 maximum", ("--model", "\u009f")),
        )
        for label, tail in invalid_values:
            arguments = ["ping", "openai", *tail]
            with self.subTest(label=label, arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout, reference.stderr), expected)
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), expected)
                self.assertEqual((reference_changes, actual_changes), ([], []))

    def test_model_help_and_syntax_precedence_remain_unchanged(self):
        arguments = ["ping", "openai", "--model", "", "--help"]
        reference, reference_changes = isolated_run(
            ORACLE, arguments, "prodex", "ping-model-help-oracle"
        )
        actual, actual_changes = isolated_run(
            MODEX, arguments, "modex", "ping-model-help-modex"
        )
        self.assertEqual((reference.returncode, reference.stderr), (0, b""))
        self.assertEqual(
            (actual.returncode, actual.stdout, actual.stderr),
            (reference.returncode, map_executable(reference.stdout), reference.stderr),
        )
        self.assertEqual((reference_changes, actual_changes), ([], []))

        reference, reference_changes = isolated_run(
            ORACLE, ["ping", "openai", "--model", "", "--bad"], "prodex", "ping-model-syntax-oracle"
        )
        actual, actual_changes = isolated_run(
            MODEX, ["ping", "openai", "--model", "", "--bad"], "modex", "ping-model-syntax-modex"
        )
        self.assertEqual((reference.returncode, actual.returncode), (2, 2))
        self.assertEqual((actual.stdout, actual.stderr), (reference.stdout, map_executable(reference.stderr)))
        self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_valid_probe_options_remain_guarded(self):
        for tail in (
            (),
            ("--json",),
            ("--profile", "synthetic-profile"),
            ("--model", "gpt-4.1"),
            ("--model", "gpt\u2028mini"),
            ("--model", "\u200bgpt-4.1"),
        ):
            result, changes = isolated_run(MODEX, ["ping", "openai", *tail], "modex", "ping-guard")
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (1, b"", b"Error: this Modex development build has not implemented the requested command\n"))
            self.assertEqual(changes, [])

    def test_base_url_scheme_precedence_matches_release_without_mutation(self):
        base_error = (
            b"Error: ping upstream base URL must be an http(s) URL with host and no "
            b"credentials, query, or fragment\n"
        )
        relative_error = base_error[:-1] + b": relative URL without a base\n"
        model_error = b"Error: --model must be nonempty and contain no control characters\n"
        for label, base_args, model, expected in (
            ("invalid scheme before empty model", ("--base-url", "ftp://example.test/v1"), "", base_error),
            ("attached invalid scheme before valid model", ("--base-url=ftp://example.test/v1",), "gpt-4.1", base_error),
            ("empty URL before empty model", ("--base-url", ""), "", relative_error),
            ("missing scheme before empty model", ("--base-url", "example.test/v1"), "", relative_error),
            ("network path before empty model", ("--base-url", "//example.test/v1"), "", relative_error),
            ("relative path before empty model", ("--base-url", "/v1"), "", relative_error),
            ("malformed scheme before empty model", ("--base-url", "1https://example.test/v1"), "", relative_error),
            ("malformed punctuation scheme before empty model", ("--base-url", "ht_tp://example.test/v1"), "", relative_error),
            ("scheme with space before empty model", ("--base-url", "ht tp://example.test/v1"), "", relative_error),
            ("spaces only before empty model", ("--base-url", "   "), "", relative_error),
            ("valid URL control", ("--base-url", "https://example.test/v1"), "", model_error),
            ("surrounding URL whitespace control", ("--base-url", " https://example.test/v1 "), "", model_error),
            ("surrounding CR LF control", ("--base-url", "\r\nhttps://example.test/v1\r\n"), "", model_error),
            ("URL TAB removal control", ("--base-url", "ht\ttps://example.test/v1"), "", model_error),
            ("URL LF scheme control", ("--base-url", "ht\nps://example.test/v1"), "", base_error),
            ("URL CR scheme control", ("--base-url", "ht\rps://example.test/v1"), "", base_error),
            ("normalized special URL control", ("--base-url", "http:///v1"), "", model_error),
            ("normalized HTTPS special URL control", ("--base-url", "https:///v1"), "", model_error),
        ):
            arguments = ["ping", "openai", *base_args, "--model", model]
            with self.subTest(label=label):
                reference, reference_changes = isolated_run(
                    ORACLE, arguments, "prodex", "ping-url-precedence-oracle"
                )
                actual, actual_changes = isolated_run(
                    MODEX, arguments, "modex", "ping-url-precedence-modex"
                )
                self.assertEqual((reference.returncode, reference.stdout, reference.stderr),
                                 (1, b"", expected))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (1, b"", expected))
                self.assertEqual((reference_changes, actual_changes), ([], []))

    def test_unimplemented_url_validation_mismatches_remain_visible(self):
        base_error = (
            b"Error: ping upstream base URL must be an http(s) URL with host and no "
            b"credentials, query, or fragment\n"
        )
        model_error = b"Error: --model must be nonempty and contain no control characters\n"
        cases = (
            ("empty host", "https://", base_error[:-1] + b": empty host\n"),
            ("query without host", "https://?x", base_error[:-1] + b": empty host\n"),
            ("invalid port", "https://example.test:abc/v1", base_error[:-1] + b": invalid port number\n"),
            ("credentials", "https://user:pass@example.test/v1", base_error),
            ("query", "https://example.test/v1?q=x", base_error),
            ("fragment", "https://example.test/v1#x", base_error),
        )
        for label, base_url, expected_reference in cases:
            arguments = ["ping", "openai", "--base-url", base_url, "--model", ""]
            with self.subTest(label=label):
                reference, reference_changes = isolated_run(
                    ORACLE, arguments, "prodex", "ping-url-gap-oracle"
                )
                actual, actual_changes = isolated_run(
                    MODEX, arguments, "modex", "ping-url-gap-modex"
                )
                self.assertEqual((reference.returncode, reference.stdout, reference.stderr),
                                 (1, b"", expected_reference))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (1, b"", model_error))
                self.assertEqual((reference_changes, actual_changes), ([], []))


if __name__ == "__main__":
    unittest.main()
