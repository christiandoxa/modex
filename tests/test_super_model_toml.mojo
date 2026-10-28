from std.collections import List
from std.testing import assert_equal

from modex.super_launch import _toml_model_literal
from modex.toml import TOMLDocument


def main() raises:
    var values: List[String] = [
        String("a\tb"),
        "a\\tb",
        "quote\"back\\slash",
        "a\r\x01\x1b\x7f",
        "a\x00b",
        "safe\nmodel_provider=\"attacker\"",
    ]
    for value in values:
        var config = TOMLDocument("model=" + _toml_model_literal(value) + "\n")
        assert_equal(config.string(config.get(config.root, "model")), value)
        assert_equal(config.get(config.root, "model_provider"), -1)
    assert_equal(_toml_model_literal("a\tb"), "\"a\tb\"")
    assert_equal(_toml_model_literal("a\\tb"), "\"a\\\\tb\"")
    print("Super model TOML literal checks: PASS")
