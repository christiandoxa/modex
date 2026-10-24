from std.math import isfinite
from std.testing import assert_true

from modex.json_float import json_float


def main() raises:
    assert_true(json_float("0") == 0.0)
    assert_true(json_float("-0") == 0.0 and (1.0 / json_float("-0")) < 0.0)
    assert_true(json_float("123") == 123.0)
    assert_true(json_float("1.25") == 1.25)
    assert_true(json_float("-42.5") == -42.5)
    assert_true(json_float("1e15") == 1e15)
    assert_true(json_float("1e-5") == 1e-5)
    assert_true(json_float("1e-7") == 1e-7)
    assert_true(json_float("4.9406564584124654e-324") > 0.0)
    assert_true(json_float("1e-400") == 0.0)
    assert_true(json_float("0." + String("0") * 100_000 + "1e100001") == 1.0)
    assert_true(isfinite(json_float("1.7976931348623157e308")))
    var rejected = False
    try:
        _ = json_float("1e400")
    except:
        rejected = True
    assert_true(rejected)
    assert_true(isfinite(json_float("18446744073709551616")))
    print("native JSON float parsing: PASS")
