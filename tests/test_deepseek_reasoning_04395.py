"""Keep the 0.439.2 low-effort divergence visible against 0.166.0 behavior."""

import hashlib
import json
import unittest
from unittest.mock import patch

import test_super_launch
from test_cli import (MODEX, ORACLE, ORACLE_SHA256, HISTORICAL_04395_ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256)


CASES = {
    "reasoning-low-flat": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning_effort": "low"},
        "low",
        "enabled",
    ),
    "reasoning-low-nested": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning": {"effort": "low"}},
        "low",
        "enabled",
    ),
    "reasoning-low-nested-precedence": (
        {
            "model": "deepseek-chat",
            "input": "synthetic prompt",
            "reasoning_effort": "high",
            "reasoning": {"effort": "low"},
        },
        "low",
        "enabled",
    ),
    "reasoning-low-trimmed": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning": {"effort": " \u2003LoW\u2003 "}},
        "low",
        "enabled",
    ),
    "reasoning-low-fallback-messages": (
        {
            "model": "deepseek-chat",
            "input": "synthetic prompt",
            "reasoning_effort": "low",
            "tool_choice": "required",
            "tools": [{"type": "custom", "name": "lookup", "format": {"type": "text"}}],
        },
        "low",
        "enabled",
    ),
    "reasoning-medium": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning_effort": "medium"},
        "high",
        "enabled",
    ),
    "reasoning-xhigh": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning_effort": "xhigh"},
        "max",
        "enabled",
    ),
    "reasoning-minimal": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning_effort": "minimal"},
        None,
        "disabled",
    ),
    "reasoning-none": (
        {"model": "deepseek-chat", "input": "synthetic prompt", "reasoning_effort": "none"},
        None,
        "disabled",
    ),
    "reasoning-direct-chat-low": (
        {
            "model": "flash",
            "messages": [{"role": "user", "content": "synthetic prompt"}],
            "reasoning_effort": "low",
        },
        "low",
        None,
    ),
}


def _replace_once(source, old, new):
    if source.count(old) != 1:
        raise AssertionError("Expected one matching Codex harness line")
    return source.replace(old, new)


def _reasoning_codex():
    source = test_super_launch.CODEX
    target = 'target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + ("/chat/completions?synthetic=1" if passthrough else "/responses"))'
    source = _replace_once(
        source,
        target,
        'direct_chat = scenario == "reasoning-direct-chat-low"\n'
        + 'target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + ("/chat/completions?synthetic=1" if passthrough or direct_chat else "/responses"))',
    )
    body = 'body = b"\\x00synthetic\\xff" if passthrough else json.dumps({"model":"deepseek-chat","input":"synthetic prompt","stream":scenario == "stream"},separators=(",",":")).encode()'
    replacement = (
        'body = b"\\x00synthetic\\xff" if passthrough else json.dumps('
        + repr({scenario: request for scenario, (request, _, _) in CASES.items()})
        + '[scenario],separators=(",",":")).encode()'
    )
    return _replace_once(source, body, replacement)


class DeepseekReasoning04395Tests(unittest.TestCase):
    def test_reasoning_wire_mapping_keeps_historical_low_effort_divergence(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertEqual(hashlib.sha256(HISTORICAL_04395_ORACLE.read_bytes()).hexdigest(),
                         HISTORICAL_04395_ORACLE_SHA256)
        harness = test_super_launch.SuperLaunchTests()
        observed = {}
        with patch.object(test_super_launch, "CODEX", _reasoning_codex()):
            for scenario, (_, effort, thinking) in CASES.items():
                records = []
                for binary in (ORACLE, HISTORICAL_04395_ORACLE, MODEX):
                    result, _, upstream, _ = harness.run_launch(binary=binary, scenario=scenario)
                    self.assertEqual(
                        (result.returncode, result.stdout),
                        (0, b"synthetic-client-complete\n"),
                        f"{scenario}: {result.stderr!r}",
                    )
                    self.assertEqual(len(upstream), 1, scenario)
                    records.append(upstream[0])
                baseline, historical, modex = records
                self.assertEqual(historical["path"], baseline["path"], scenario)
                self.assertEqual(modex["path"], baseline["path"], scenario)
                baseline_body = json.loads(bytes.fromhex(baseline["body"]))
                historical_body = json.loads(bytes.fromhex(historical["body"]))
                modex_body = json.loads(bytes.fromhex(modex["body"]))
                if scenario == "reasoning-direct-chat-low":
                    self.assertEqual(baseline["path"], "/v1/chat/completions?synthetic=1")
                    self.assertEqual(baseline_body, CASES[scenario][0])
                    self.assertEqual(historical_body, baseline_body)
                    self.assertEqual(modex_body, baseline_body)
                else:
                    self.assertEqual(baseline["path"], "/v1/chat/completions")
                    # Prodex 0.439.2 promoted low to high; 0.439.5 and the active
                    # 0.166.0 target preserve low.
                    historical_04392_effort = "high" if effort == "low" else effort
                    self.assertEqual(baseline_body.get("reasoning_effort"), historical_04392_effort, scenario)
                    self.assertEqual(historical_body.get("reasoning_effort"), effort, scenario)
                    self.assertEqual(modex_body.get("reasoning_effort"), effort, scenario)
                    self.assertEqual(baseline_body.get("thinking"), {"type": thinking}, scenario)
                    self.assertEqual(historical_body.get("thinking"), {"type": thinking}, scenario)
                    self.assertEqual(modex_body.get("thinking"), {"type": thinking}, scenario)
                    normalized_baseline = dict(baseline_body)
                    if effort == "low":
                        normalized_baseline["reasoning_effort"] = "low"
                    self.assertEqual(normalized_baseline, historical_body, scenario)
                    self.assertEqual(historical_body, modex_body, scenario)
                observed[scenario] = baseline_body
        self.assertEqual(len(observed), len(CASES))


if __name__ == "__main__":
    unittest.main()
