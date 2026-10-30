"""Super extraction preserves Codex arguments and validates before startup."""

from std.collections import List
from std.testing import assert_equal, assert_true

from modex.super_cli import SuperOptions, _valid_float_value, parse_super_arguments, validate_super_options


def rejects(args: List[String], expected: String) raises:
    var failed = False
    try:
        var options = parse_super_arguments(args, "modex")
        validate_super_options(options)
    except error:
        failed = True
        assert_equal(String(error), expected)
    assert_true(failed)


def main() raises:
    var options = parse_super_arguments([String("modex"), "s", "--provider=deepseek", "exec", "--model", "fixture-model", "--", "--api-key", "literal-key"], "modex")
    assert_equal(options.value("--provider"), "deepseek")
    assert_equal(options.value("--model"), "fixture-model")
    assert_equal(len(options.codex_args), 4)
    assert_equal(options.codex_args[0], "exec")
    assert_equal(options.codex_args[1], "--")
    assert_equal(options.codex_args[2], "--api-key")
    assert_equal(options.codex_args[3], "literal-key")
    validate_super_options(options)
    for name in ["--rollout-budget-sampling-weight", "--rollout-budget-prefill-weight"]:
        for value in ["+0", "-0", "NaN", "+infinity", "1e9999", "1e999999999999999999999999999999", "1e-9999", "1.", ".1"]:
            options = parse_super_arguments([String("modex"), "super", name, value], "modex")
            assert_equal(options.value(name), value)
        for value in ["infinite", "in", "1f", "0x1p0", "1.0tail"]:
            var error = "error: invalid value '" + value + "' for '" + name + " <WEIGHT>': invalid float literal\n\nFor more information, try '--help'.\n"
            rejects([String("modex"), "super", name, value], error)
        rejects([String("modex"), "super", name, ""], "error: invalid value '' for '" + name + " <WEIGHT>': cannot parse float from empty string\n\nFor more information, try '--help'.\n")
        for value in ["1e", "1f", "in", "0x1p0"]:
            rejects([String("modex"), "super", "exec", name, value], "invalid float literal")
        var nul_value = String("1") + chr(0)
        assert_true(not _valid_float_value(nul_value))
    options = parse_super_arguments([String("modex"), "super", "--profile", "initial", "019c9e3d-45a0-7ad0-a6ee-b194ac2d44f9", "--profile", "tail", "--no-auto-rotate", "--auto-rotate"], "modex")
    assert_equal(options.value("--profile"), "initial")
    assert_true(options.has("--auto-rotate"))
    assert_true(not options.has("--no-auto-rotate"))
    options = parse_super_arguments([String("modex"), "super", "--", "--presidio", "--no-presidio"], "modex")
    assert_true(not options.has("--presidio"))
    assert_equal(len(options.codex_args), 2)
    options = parse_super_arguments([String("modex"), "super", "-pmain", "--local-model=m", "--provider=claude"], "modex")
    assert_equal(options.value("--profile"), "main")
    assert_equal(options.value("--model"), "m")
    assert_equal(options.value("--provider"), "anthropic")
    options = parse_super_arguments([String("modex"), "super", "exec", "--url", "http://127.0.0.1:8131/v1"], "modex")
    validate_super_options(options)
    options = parse_super_arguments([String("modex"), "super", "exec", "--base-url", "https://api.example.test/v1"], "modex")
    validate_super_options(options)
    options = parse_super_arguments([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-provider", "local", "--sub-agent-url", "https://[::1]:8131/v1"], "modex")
    validate_super_options(options)
    var raw_sub_agent_url = " https://[::1]:8131/v1 "
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-provider", "local", "--sub-agent-url", raw_sub_agent_url], "modex")
    assert_equal(options.value("--sub-agent-url"), raw_sub_agent_url)
    validate_super_options(options)
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-model", "  雪 model  "], "modex")
    assert_equal(options.value("--sub-agent-model"), "  雪 model  ")
    validate_super_options(options)
    rejects([String("modex"), "super", "--sub-agent", "--sub-agent-model", "  "], "error: invalid value '  ' for '--sub-agent-model <MODEL>': --sub-agent-model must be nonempty\n\nFor more information, try '--help'.\n")
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-model-reasoning-effort", " HIGH "], "modex")
    assert_equal(options.value("--sub-agent-model-reasoning-effort"), "high")
    validate_super_options(options)
    rejects([String("modex"), "super", "--sub-agent", "--sub-agent-model-reasoning-effort", " INSTANT "], "error: invalid value ' INSTANT ' for '--sub-agent-model-reasoning-effort <EFFORT>': invalid sub-agent reasoning effort: expected none, minimal, low, medium, high, xhigh, max, or ultra, got \"instant\"\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "--sub-agent", "--sub-agent-model-reasoning-effort", "İNSTANT"], "error: invalid value 'İNSTANT' for '--sub-agent-model-reasoning-effort <EFFORT>': invalid sub-agent reasoning effort: expected none, minimal, low, medium, high, xhigh, max, or ultra, got \"İnstant\"\n\nFor more information, try '--help'.\n")
    for value in ["default", "4", "8", "16", "32", "23", "64"]:
        options = parse_super_arguments([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", value], "modex")
        assert_equal(options.value("--sub-agent-max-concurrency"), value)
        validate_super_options(options)
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-max-concurrency", " 1 "], "modex")
    assert_equal(options.value("--sub-agent-max-concurrency"), "1")
    validate_super_options(options)
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-max-concurrency", " default "], "modex")
    assert_equal(options.value("--sub-agent-max-concurrency"), "default")
    validate_super_options(options)
    for value, expected in [(" 01 ", "1"), (" default ", "default"), ("　64　", "64")]:
        options = parse_super_arguments([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", value], "modex")
        assert_equal(options.value("--sub-agent-max-concurrency"), expected)
        validate_super_options(options)
    rejects([String("modex"), "super", "exec", "--sub-agent-model", "m"], "sub-agent detail flags require explicit --sub-agent")
    rejects([String("modex"), "super", "--sub-agent", "--no-sub-agent"], "error: the argument '--sub-agent' cannot be used with '--no-sub-agent'\n\nUsage: modex super --sub-agent [CODEX_ARG]...\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--no-sub-agent"], "--sub-agent conflicts with --no-sub-agent")
    rejects([String("modex"), "super", "--provider", "deepseek", "--url", "http://127.0.0.1:8131"], "error: the argument '--provider <PROVIDER>' cannot be used with '--url <URL>'\n\nUsage: modex super --provider <PROVIDER> [CODEX_ARG]...\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "exec", "--provider", "deepseek", "--url", "http://127.0.0.1:8131"], "--provider conflicts with --url")
    rejects([String("modex"), "super", "--api-key", "synthetic-key"], "error: the following required arguments were not provided:\n  --provider <PROVIDER>\n\nUsage: modex super --provider <PROVIDER> --api-key <KEY> [CODEX_ARG]...\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "exec", "--api-key", "synthetic-key"], "--api-key requires --provider")
    rejects([String("modex"), "super", "--context-window", "16384"], "error: the following required arguments were not provided:\n  <--provider <PROVIDER>|--url <URL>>\n\nUsage: modex super --context-window <TOKENS> <--provider <PROVIDER>|--url <URL>> [CODEX_ARG]...\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "exec", "--context-window", "16384"], "context-window options require --provider or --url")
    rejects([String("modex"), "super", "--auto-compact-token-limit", "512"], "error: the following required arguments were not provided:\n  <--provider <PROVIDER>|--url <URL>>\n\nUsage: modex super --auto-compact-token-limit <TOKENS> <--provider <PROVIDER>|--url <URL>> [CODEX_ARG]...\n\nFor more information, try '--help'.\n")
    rejects([String("modex"), "super", "exec", "--auto-compact-token-limit", "512"], "context-window options require --provider or --url")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-provider", "LOCAL_OPENAI"], "local sub-agent provider requires --sub-agent-url")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-url", "http://127.0.0.1:8131"], "--sub-agent-url requires --sub-agent-provider local")
    rejects([String("modex"), "super", "exec", "--url", "http://synthetic-user:synthetic-secret@127.0.0.1:8131"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://%zz.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://foo%2Fbar.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://a%40b.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://a|b.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://a%EF%BC%8Fb.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "https://a%FFb.example.test/path"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    options = parse_super_arguments([String("modex"), "super", "exec", "--url", "https://%65xample.test/path"], "modex")
    validate_super_options(options)
    rejects([String("modex"), "super", "exec", "--base-url", "https://api.example.test/v1?synthetic-secret"], "invalid --base-url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-provider", "local", "--sub-agent-url", "ftp://127.0.0.1:8131"], "invalid --sub-agent-url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--url", "http:///missing-host"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "0"], "maximum active sub-agents must be between 1 and 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "65"], "maximum active sub-agents must be between 1 and 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "unknown"], "invalid maximum active sub-agents: expected default or an integer from 1 to 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "99999999999999999999"], "invalid maximum active sub-agents: expected an integer from 1 to 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", " +1 "], "invalid maximum active sub-agents: expected default or an integer from 1 to 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", " 99999999999999999999x "], "invalid maximum active sub-agents: expected default or an integer from 1 to 64")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-max-concurrency", " 65 "], "maximum active sub-agents must be between 1 and 64")
    rejects([String("modex"), "super", "gui", "--sub-agent"], "--sub-agent is unsupported with the Codex Desktop frontend")
    print("Super extraction, literal boundaries, aliases, and launch validation: PASS")
