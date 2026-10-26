from std.testing import assert_equal

from modex.inspection_cli import inspection_usage


def main() raises:
    assert_equal(inspection_usage("current", ""), "current")
    assert_equal(inspection_usage("info", ""), "info [OPTIONS]")
    assert_equal(inspection_usage("status", ""), "status [OPTIONS]")
    print("inspection CLI empty argv0 usage fallback: PASS")
