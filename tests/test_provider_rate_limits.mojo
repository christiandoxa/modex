from std.collections import List
from std.testing import assert_equal

from modex.provider_rate_limits import deepseek_codex_rate_limit_headers


def values(headers: List[Tuple[String, String]], name: String) -> List[String]:
    var output = List[String]()
    for key, value in headers:
        if key == name:
            output.append(value)
    return output^


def rate_limit_headers() raises:
    var headers: List[Tuple[String, String]] = [
        ("X-RateLimit-Limit-Requests", "100"),
        ("x-ratelimit-remaining-requests", "\t40\t"),
        ("x-ratelimit-reset-requests", "1700000000000"),
        ("x-ratelimit-limit-tokens", "80"),
        ("x-ratelimit-remaining-tokens", "60"),
        ("x-ratelimit-reset-tokens", "1700000000000"),
    ]
    var projected = deepseek_codex_rate_limit_headers(headers)
    assert_equal(values(projected, "x-deepseek-requests-primary-used-percent"), ["60"])
    assert_equal(values(projected, "x-deepseek-tokens-primary-used-percent"), ["25"])
    assert_equal(values(projected, "x-deepseek-requests-primary-reset-at"), ["1700000000"])

    for invalid in [0, 10, 13, 31, 127, 128]:
        headers[0][1] = chr(invalid) + "100"
        projected = deepseek_codex_rate_limit_headers(headers)
        assert_equal(len(values(projected, "x-deepseek-requests-limit-name")), 0)
        assert_equal(values(projected, "x-deepseek-tokens-primary-used-percent"), ["25"])
    headers[0][1] = "100"

    var whitespace = chr(8195)
    headers[2][1] = whitespace + "1700000000000" + whitespace
    projected = deepseek_codex_rate_limit_headers(headers)
    assert_equal(values(projected, "x-deepseek-requests-primary-used-percent"), ["60"])
    assert_equal(len(values(projected, "x-deepseek-requests-primary-reset-at")), 0)
    assert_equal(values(projected, "x-deepseek-tokens-primary-reset-at"), ["1700000000"])

    headers[0][1] = whitespace + "100" + whitespace
    projected = deepseek_codex_rate_limit_headers(headers)
    assert_equal(len(values(projected, "x-deepseek-requests-limit-name")), 0)
    assert_equal(values(projected, "x-deepseek-tokens-primary-used-percent"), ["25"])


def main() raises:
    rate_limit_headers()
