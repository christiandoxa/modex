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
