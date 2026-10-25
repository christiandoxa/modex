"""Native configuration projection checks traced to the frozen runtime policy."""

from std.collections import List
from std.testing import assert_equal

from modex.app_server_args import project_app_server_config_args
from modex.toml import TOMLDocument


def _check(arguments: List[String], expected: List[String], include_inline_config: Bool = True) raises:
    var actual = project_app_server_config_args(arguments, include_inline_config)
    assert_equal(len(actual), len(expected))
    for index in range(len(expected)):
        assert_equal(actual[index], expected[index])


def main() raises:
    var arguments: List[String] = ["--model", "gpt-6.1-sol", "--config=projects={a=1}", "--strict-config", "--enable", "web_search", "resume"]
    _check(arguments, [String("-c"), "model=\"gpt-6.1-sol\"", "--config=projects={a=1}", "--strict-config", "--enable", "web_search"])
    _check(arguments, [String("-c"), "model=\"gpt-6.1-sol\"", "--strict-config", "--enable", "web_search"], False)
    _check([String("--model=雪とé")], [String("-c"), "model=\"雪とé\""])
    _check([String("--model=")], [String("-c"), "model=\"\""])
    _check([String("-m"), "--strict-config"], [String("-c"), "model=\"--strict-config\""])
    _check([String("-c"), "model='x'", "--disable", "a", "--code-mode-host", "b", "--config", "c=d"], [String("-c"), "model='x'", "--disable", "a", "--code-mode-host", "b", "--config", "c=d"], False)
    _check([String("--config="), "-c=", "--config=x", "-c=y"], [String("--config="), "-c=", "--config=x", "-c=y"])
    _check([String("--config=x"), "-c=y", "--enable=z", "--disable=a", "-mshort", "-cshort"], List[String](), False)
    _check([String("--"), "prompt", "--strict-config", "--model", "x"], [String("--strict-config"), "-c", "model=\"x\""])
    for flag in [String("-c"), "--config", "--enable", "--disable", "--code-mode-host", "-m", "--model"]:
        _check([flag], List[String]())
    for value in [String("quote\"and\\slash"), "line\ncarriage\rtab\t", "\b\f\x00\x1b\x7f", "雪とé", ""]:
        var projected = project_app_server_config_args([String("--model"), value], True)
        var config = TOMLDocument(projected[1] + "\n")
        assert_equal(config.string(config.get(config.root, "model")), value)
    print("app-server configuration projection checks: PASS")
