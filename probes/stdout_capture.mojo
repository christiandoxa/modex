"""Development probe only; Modex does not use shell stdout capture."""

from std.subprocess import run
from std.testing import assert_equal


def main() raises:
    var output = run("printf 'synthetic-stdout'")
    assert_equal(output, "synthetic-stdout")
    print("official stdout capture: PASS")
