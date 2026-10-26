"""Record real Super idle failures; exit 1 while exact behavior differs."""

import hashlib
import json
from test_cli import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_deepseek_continuation import json_bytes, observe_turns


def capture():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise AssertionError("oracle does not match pinned Prodex 0.439.1")
    chunk = {"id": "synthetic-idle-chat", "created": 42, "model": "deepseek-chat",
             "choices": [{"index": 0, "delta": {"content": "kept before idle"}}]}
    cases = []
    for name, body in (("before_first_event", b""),
                       ("after_text_delta", b"data: " + json_bytes(chunk) + b"\n\n")):
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, [{"model": "deepseek-chat",
                "input": "synthetic idle deadline", "stream": True}], [{"status": 200,
                "content_type": "text/event-stream", "body": body, "chunked": True,
                "hold_open": True}], idle_timeout_ms=100)
            if len(upstream) != 1 or len(responses) != 1:
                raise AssertionError("timeout probe must capture one response and one POST")
            payload = bytes.fromhex(responses[0]["body"])
            events = [json.loads(line[6:]) for line in payload.splitlines() if line.startswith(b"data: ")]
            observations.append({"binary": str(binary), "status": responses[0]["status"],
                "upstream_posts": len(upstream), "event_types": [event["type"] for event in events],
                "deltas": [event["delta"] for event in events if event["type"] == "response.output_text.delta"],
                "failure": events[-1]["response"]["error"] if events else None,
                "plain_body": None if events else payload.decode("utf-8")})
        comparable = [{key: value for key, value in row.items() if key != "binary"} for row in observations]
        cases.append({"name": name, "matches": comparable[0] == comparable[1],
                      "observations": observations})
    return {"baseline_commit": "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3",
            "oracle_sha256": ORACLE_SHA256, "idle_timeout_ms": 100,
            "modex_sha256": hashlib.sha256(MODEX.read_bytes()).hexdigest(),
            "status": "PASS" if all(case["matches"] for case in cases) else "FAIL",
            "limit": "Small synthetic idle probe; exact release error may depend on which transport deadline fires first.",
            "cases": cases}


if __name__ == "__main__":
    result = capture()
    target = ROOT / "docs/evidence/checkpoint9-timeout-mismatch.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
