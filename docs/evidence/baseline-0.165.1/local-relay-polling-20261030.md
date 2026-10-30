# Local relay polling and saturation measurements

The pinned Prodex 0.165.1 and 0.439.2 source commits use TinyHTTP's
`TaskPool`: `spawn` starts a thread when no worker is waiting, with no fixed
connection or queue cap. Modex keeps its bounded worker and socket caps. This
comparison changes only how often the Modex listener checks parked sockets.

The trial changes the full-overflow no-progress sleep from 1 ms to 5 ms. When
no worker work is pending but at least one socket is parked, the accept wait
changes from 100 ms to 10 ms. The other waits remain 5 ms with pending work,
100 ms for an empty listener with a parent channel, and 1,000 ms for an empty
standalone listener. The full-overflow wait can add at most 4 ms nominal delay
per no-progress scan. Admission capacity, eviction, framing, worker count and
the saturated starvation boundary remain unchanged.

## References and setup

The source trace used Prodex commits `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The checksum-verified Linux
x86-64 binaries were 0.165.1
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
0.439.2 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
The Modex control was built from parent commit
`2d6305551336ca743103ac5f9f78809f0f1c6818`; the trial used the same source
plus the polling changes.

Every probe launched the real Super process with a synthetic Codex client and
loopback upstream, isolated temporary homes, and ephemeral ports. No provider
credentials or paid traffic were used. The comparisons below use three matched
runs per binary. Process CPU uses `/proc` user and system ticks, which have
10 ms resolution. RSS sums per-process `VmRSS` and may count shared pages.

## Request timing and keep-alive throughput

| Probe | Prodex 0.165.1 | Prodex 0.439.2 | Modex parent | Modex trial |
|---|---:|---:|---:|---:|
| One normal response, elapsed ms | 1 [1–2] | 1 [1–1] | 6 [2–7] | 5 [2–6] |
| Four-part request head, 30 ms between parts, elapsed ms | 92 [92–97] | 92 [92–93] | 105 [105–106] | 93 [92–93] |
| 71-request keep-alive/churn probe, elapsed ms | 61 [59–63] | 106 [62–268] | 3,350 [3,335–3,444] | 1,565 [1,565–1,599] |
| Same probe, whole process wall ms | 466 [461–485] | 580 [453–1,077] | 3,685 [3,672–3,736] | 1,804 [1,788–1,855] |

The keep-alive probe completes 39 reused requests and 24 fresh-client requests;
all 71 upstream records are present, every response is 200, and no client
reports an error. The Modex trial cuts its median probe elapsed time by 53%.
Total process wall time remains about 3–4 times the pinned-process medians.
The normal single-response and fragmented-head probes show no added latency in
this sample.

## CPU and descriptors

| Load, 1 s CPU sample | Prodex 0.165.1 | Prodex 0.439.2 | Modex parent | Modex trial |
|---|---:|---:|---:|---:|
| 128 parked idle keep-alive sockets, CPU s | 0.00 [0.00–0.00] | 0.00 [0.00–0.00] | 0.04 [0.03–0.05] | 0.05 [0.05–0.07] |
| 136 partial heads plus 7 incomplete-body blockers, CPU s | 0.01 [0.00–0.01] | 0.00 [0.00–0.00] | 0.33 [0.29–0.34] | 0.13 [0.10–0.14] |
| Same loads, Modex FD delta | 432 | 288 | 127 / 143 | 127 / 143 |

With 128 parked sockets, the trial adds about 0.01 CPU seconds per second at
the median; the descriptor count remains 127. Under the partial-head flood,
the 5 ms scan reduces median Modex CPU by 0.20 seconds per second, about 61%,
with the same 143 descriptors. One-second measurements are local samples,
not host-independent resource limits. The final seven-test rerun added a
0.14-second trial sample; the three matched trial samples were 0.10, 0.13 and
0.13 seconds per second.

## Saturated admission and parent EOF

The release processes served both healthy keep-alive requests before blockers
closed in all three runs. Both Modex builds served neither request before
release. Their first response medians were 3,093 ms [3,003–3,095] before the
trial and 3,092 ms [3,085–3,093] after it. These times include the fixture's
two-second hold and one-second sample; they show the same starvation boundary,
not ordinary request latency. Both Modex builds stayed at 143 client FDs.

Parent shutdown was also repeated three times with one held keep-alive socket
and with a stalled synthetic upstream. All processes exited and the Modex
upstream socket closed. Whole-process elapsed times were:

| EOF control, ms | Prodex 0.165.1 | Prodex 0.439.2 | Modex parent | Modex trial |
|---|---:|---:|---:|---:|
| Held idle keep-alive client, median [range] | 397 [396–401] | 390 [382–483] | 228 [197–309] | 207 [203–208] |
| Stalled provider request, median [range] | 403 [403–406] | 395 [390–397] | 207 [202–209] | 205 [200–207] |

These include process startup and do not isolate EOF observation time. The
30 ms fragmented-head control exercises slow completion, not expiry of the
120-second request-head deadline. That deadline's expiry and non-Linux targets
remain unverified.

## Reproduction

After `make build` and `make UNIT_BUILD_PROGRAMS=local_rewrite_driver unit-build`,
the checked-in process controls are:

```sh
PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_admission_eviction_compares_preconnected_idle_and_keepalive_sockets \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_ready_parked_clients_are_served_during_new_client_churn \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_partial_request_headers_still_complete_before_relay_dispatch \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_partial_reused_request_does_not_block_second_client \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_parent_shutdown_exits_while_idle_keep_alive_socket_is_held \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_parent_eof_interrupts_a_stalled_provider_request \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_worker_count_controls_parallel_provider_stalls
```

The final seven selected tests passed in 43.507 seconds; the admission and
cross-release fairness pair passed again in 21.643 seconds. The production
build, local rewrite driver build, 71-file dependency audit, and
`git diff --check` passed. A worker-count test attempt before the local driver
was built failed at setup; the selected suite passed after that driver build.

The repeated timing and resource samples use the same module's `run_probe`
helper with explicit paths to the two Modex builds and the checksum-pinned
release binaries. This evidence covers Linux x86-64 only; it does not establish
full admission, resource, security, or platform parity. The unbounded release
queue still serves traffic that the Modex cap leaves waiting.
