# Managed Ponytail integrity validation safety blocker

The proposed read-only validator is not connected to `doctor --install`.
Mojo 1.2.0's documented `std.os.listdir` returns a complete `List[String]`, so
checking the entry count after calling it cannot bound directory-listing memory.
The documented `std.os.process.Process` API kills only its direct child and
does not expose process-group creation or termination. A PATH-selected Node
probe could therefore leave descendants holding capture pipes after failure.

There is also an aggregate-cap race in the prototype: it totals file sizes
during traversal, then re-stats and reads files later without carrying the
traversal-time file identity forward. A replaced or grown file could evade the
tree-wide limit or make the hash describe a different snapshot.

No official standard-library streaming directory iterator or safe process-group
spawn API was found. Under Modex's no-new-bindings rule, these limits prevent
the proposed tree walk from making a bounded resource or cleanup claim. Keep
the existing degraded Ponytail status until those guarantees can be provided;
do not count this slice as parity.

References: [Mojo 1.2 `listdir`](https://mojolang.org/docs/std/os/os/listdir/),
[Mojo 1.2 `Process`](https://mojolang.org/docs/std/os/process/Process/).
