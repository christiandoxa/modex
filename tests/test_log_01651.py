"""Run the existing bounded logging suite against pinned Prodex 0.165.1."""

import hashlib
import os
from pathlib import Path
import unittest

import test_cli
import test_log_cli
import test_logs
import test_log_operational
import test_log_payload
import test_log_payload_render
import test_log_redaction
import test_log_runtime
import test_log_text
import test_log_timestamps
import test_log_transcript


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
MODEX = Path(os.environ.get("MODEX_BINARY", Path(__file__).resolve().parents[1] / "build/modex"))

LOG_MODULES = (
    test_logs,
    test_log_operational,
    test_log_payload,
    test_log_payload_render,
    test_log_redaction,
    test_log_runtime,
    test_log_cli,
    test_log_text,
    test_log_timestamps,
    test_log_transcript,
)


class ActiveOracle01651:
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

        modules = (test_cli, *LOG_MODULES)
        cls._saved_oracle_globals = []
        for module in modules:
            saved = {}
            for name, value in (("ORACLE", ORACLE), ("ORACLE_SHA256", ORACLE_SHA256), ("MODEX", MODEX)):
                if hasattr(module, name):
                    saved[name] = getattr(module, name)
                    setattr(module, name, value)
            cls._saved_oracle_globals.append((module, saved))
        try:
            super().setUpClass()
        except BaseException:
            cls._restore_oracle_globals()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls._restore_oracle_globals()

    @classmethod
    def _restore_oracle_globals(cls):
        for module, saved in cls._saved_oracle_globals:
            for name, value in saved.items():
                setattr(module, name, value)
        cls._saved_oracle_globals = []


class LogLast01651Tests(ActiveOracle01651, test_logs.LogLastTests):
    pass


class LogCli01651Tests(ActiveOracle01651, test_log_cli.LogCliTests):
    pass


class OperationalLogProjection01651Tests(ActiveOracle01651, test_log_operational.OperationalLogProjectionTests):
    pass


class LogPayload01651Tests(ActiveOracle01651, test_log_payload.LogPayloadTests):
    pass


class LogPayloadRender01651Tests(ActiveOracle01651, test_log_payload_render.LogPayloadRenderTests):
    pass


class LogRedaction01651Tests(ActiveOracle01651, test_log_redaction.LogRedactionTests):
    pass


class LogRuntime01651Tests(ActiveOracle01651, test_log_runtime.LogRuntimeTests):
    pass


class LogText01651Tests(ActiveOracle01651, test_log_text.LogTextTests):
    pass


class LogTimestamp01651Tests(ActiveOracle01651, test_log_timestamps.LogTimestampTests):
    pass


class Transcript01651Tests(ActiveOracle01651, test_log_transcript.TranscriptTests):
    pass


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    for test_case in (
        LogLast01651Tests,
        LogCli01651Tests,
        OperationalLogProjection01651Tests,
        LogPayload01651Tests,
        LogPayloadRender01651Tests,
        LogRedaction01651Tests,
        LogRuntime01651Tests,
        LogText01651Tests,
        LogTimestamp01651Tests,
        Transcript01651Tests,
    ):
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    return suite
