# Local relay concurrency and shutdown

The pinned 0.165.1 release starts multiple local-rewrite listener workers from
`runtime_config.tuning.worker_count`; TinyHTTP captures requests separately and
queues parsed requests. The 0.439.2 source has the same worker and capture
structure. Modex previously handled one complete request at a time, so a
stalled request prevented an independent request from reaching its upstream.

The relay now runs a bounded pool of Mojo standard-library tasks, sharing its
conversation store and bindings under one lock. Accepted sockets have one owner
at a time: parked, queued, worker, completed, or closed. The owned shared
state and its immutable endpoint configuration outlive the task group. This is
necessary because casting their pointers to untracked origins does not itself
extend the lifetime of the original stack values. The task group is joined
before its state and cancellation socketpair are destroyed.

On parent EOF, the relay signals a dedicated cancellation socket and shuts down
active client sockets before joining workers. The outbound transport peeks at
the cancellation socket during connect, send, and receive waits; it does not
consume the signal or take ownership of the descriptor. Client request
half-close remains distinct from cancellation. Both the chat passthrough and
native Anthropic Messages paths use this signal.

A synthetic peer holds two chat-completions requests at a barrier. Both pinned
release processes and Modex dispatch both requests before either response is
released. A partial request on a reused connection no longer prevents a second
client from completing in the selected 0.165.1 and 0.439.2 controls. Separate
process tests end the parent while a synthetic upstream stalls before headers;
Modex exits promptly and closes the upstream for both passthrough and native
Anthropic requests. Ordinary sequential, pipelined, raw HTTP and shared-writer
controls remain covered. All homes, credentials, provider endpoints and ports in
these tests are synthetic and isolated.

This is not full concurrency or platform parity. Modex limits handler lanes to
at most eight and at most the Mojo runtime's parallelism; it does not yet honor
Prodex's worker-count configuration or its default four-to-twelve worker
range. Header capture now runs in the listener loop before handler admission;
body capture consumes a handler lane. Enough incomplete bodies can block
service. Unlike TinyHTTP's separate dynamic parser tasks, header capture is
bounded by the parked-connection cap and a 2 MiB header limit.
The existing 128 parked connections plus one overflow are bounded, whereas the
release's parsed-request queue is not. Idle connections have no expiry, and
saturation polling, first-event retries, general interruption, scheduling,
resource accounting and non-Linux targets remain unqualified. The private
`std.runtime._asyncrt` task-group API is bundled with the pinned official Mojo
1.2.0 library but is documented as unstable; upgrades require revalidation.
All six release targets remain in the denominator.

Validation on Linux x86-64 with Mojo 1.2.0: the production build and focused
native drivers passed. Before the independent SSE update, the complete selected
0.165.1 and 0.439.2 relay oracle modules passed 30 tests, including the new
barrier and parent-EOF checks. After that update, 101 shared loopback, relay,
stream and provider transport tests and 17 cross-release Anthropic stream tests
passed. The production dependency audit and test census passed. These results
qualify only the exercised controls, not the entire runtime contract.

## Failed-stream pipeline follow-up (2026-10-29)

Both pinned release processes return an unfinished chunked Anthropic failure
stream with `Connection: close`, then write a raw second 502 for a complete
queued HTTP/1.1 request on the same socket. Modex now restores the connection
to the parked listener after that incomplete stream and processes the queued
request serially. The first response remains open; it does not receive a final
chunk before the second response. The new production regression checks this
wire behavior for FIN and RST, then verifies that a separate follow-up request
still reaches the synthetic provider. This does not create concurrent writers
for a socket: the first worker finishes before the listener assigns it again.
At both Prodex 0.439.2 and historical 0.439.1 source commits, the local rewrite
pipeline finishes rejected requests through `request.respond`; a checksum-
verified 0.439.1 process control also returned `Connection: close` and the raw
502. The 0.439.1 control is historical regression evidence only.

No-pipeline/open-body, request half-close, upstream EOF/reset, eight-client
FIN/RST worker release, a full queued body, a truncated queued body, a
truncated request head, and parent EOF were checked against 0.165.1, 0.439.2,
and Modex. The full 1 MiB queued body may finish the fake client naturally after
the raw 502, so explicit parent-EOF cancellation is asserted separately for a
complete head with a partial body and for a 64-byte incomplete head. Both
controls leave no live child processes.

An earlier eight-client run returned the raw 502 on 8/8 32 KiB padded pipeline
heads for both releases and 3/8 for Modex within the 100 ms read window. The
listener could wait 100 ms in `accept` while a worker finished, delaying its
completed connection. It now checks for queued, active, and completed work and
uses a 5 ms wait while any exists. Capture remains bounded to 512 bytes per
parked socket per pass. In two subsequent eight-client FIN/RST runs, each
release and Modex returned the 502 on all eight connections. The maintained
sequential stress control requires at least six of eight in each case within
the window, while testing follow-up service and disconnect cleanup. These
timing-sensitive observations do not establish large-head admission parity.
While work is pending, the listener can perform about 200 full parked-socket
scans per second. Its existing nonblocking accept loop sleeps for 1 ms between
retries even during the longer wait; neither figure is a measured CPU cost.

Validation on Linux x86-64 with Mojo 1.2.0 passed the production build and the
three declared native test drivers:

```sh
mojo build -O3 --target-cpu=x86-64-v3 -I src src/main.mojo -o build/modex
make UNIT_BUILD_PROGRAMS='provider_chat_stream_driver loopback_http_stream_driver local_rewrite_driver' unit-build
```

The affected provider chat stream, loopback HTTP stream, and local rewrite
modules passed 54 tests; the focused pipeline/open-body/FIN/RST/EOF matrix
passed 10 tests. The production import audit passed for all 71 Mojo files, and
the test census passed for 50 native sources and 135 Python modules. A combined
90-test run initially had 87 passing tests and three setup errors for those
missing drivers; it included and passed both `test_local_rewrite_01651_oracle`
and `test_local_rewrite_04392_oracle`. The combined run was not repeated after
building the drivers, so these results do not qualify the entire runtime
contract.
