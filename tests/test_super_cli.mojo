"""Super extraction preserves Codex arguments and validates before startup."""

from std.collections import List
from std.testing import assert_equal, assert_true

from modex.super_cli import SuperOptions, parse_super_arguments, validate_super_options


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
    options = parse_super_arguments([String("modex"), "super", "--sub-agent", "--sub-agent-model", "  雪 model  "], "modex")
    assert_equal(options.value("--sub-agent-model"), "  雪 model  ")
    validate_super_options(options)
    rejects([String("modex"), "super", "--sub-agent", "--sub-agent-model", "  "], "error: invalid value '  ' for '--sub-agent-model <MODEL>': --sub-agent-model must be nonempty\n\nFor more information, try '--help'.\n")
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
    rejects([String("modex"), "super", "exec", "--sub-agent", "--no-sub-agent"], "--sub-agent conflicts with --no-sub-agent")
    rejects([String("modex"), "super", "exec", "--api-key", "synthetic-key"], "--api-key requires --provider")
    rejects([String("modex"), "super", "exec", "--context-window", "16384"], "context-window options require --provider or --url")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-provider", "local"], "local sub-agent provider requires --sub-agent-url")
    rejects([String("modex"), "super", "exec", "--sub-agent", "--sub-agent-url", "http://127.0.0.1:8131"], "--sub-agent-url requires --sub-agent-provider local")
    rejects([String("modex"), "super", "exec", "--url", "http://synthetic-user:synthetic-secret@127.0.0.1:8131"], "invalid --url: expected an absolute http(s) URL with host and no credentials, query, or fragment")
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
