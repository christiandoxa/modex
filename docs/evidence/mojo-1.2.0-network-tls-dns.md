# Mojo 1.2.0 network, TLS, and DNS standard-library audit

Audited the official Mojo 1.2.0 compiler `2016d0cd` and installed standard
library source snapshot at `/home/test-user/.cache/modex/toolchains/mojo-1.2.0-source/std`
on 2026-10-29. This is a standard-library capability check, not Modex parity
evidence.

## Findings

`std.net/__init__.mojo` says the package contains only internal building blocks
and that its public types are not yet available. Its `_sys` source provides
raw POSIX socket constants, address layouts, and C ABI wrappers for `socket`,
`bind`, `listen`, `accept`, `connect`, `send`, `recv`, `sendto`, and `recvfrom`.
These wrappers call external C symbols. Address layouts are supplied for
Linux and macOS; there is no Windows implementation. The source contains no
DNS resolver, TLS, HTTP, or WebSocket package or API. In particular, the
standard library has no `getaddrinfo`/`getnameinfo` wrapper.

`std.hash` exports general `Hashable` and `Hasher` infrastructure. Its
implementations are AHash for runtime hashing and FNV-1a for compile-time
hashing. The `Hashable` source explicitly says its hashes do not need to be
cryptographically secure. The package does not provide SHA-1, SHA-256, or
other TLS digest/cipher/certificate APIs. `std.random` describes its PRNG as
not cryptographically secure and warns against using it for keys or other
security-sensitive values; no operating-system CSPRNG API is exported.

The official `std.ffi` APIs can make direct C calls or load dynamic libraries,
but that does not add DNS or TLS support to the standard library. Declaring a
new libc resolver binding or loading OpenSSL would violate Modex's no-new-
native-bindings and no-external-implementation rules.

The private POSIX wrappers can create raw UDP sockets on Linux and macOS. A
handwritten DNS client could build on those primitives and a configured numeric
resolver address, but Mojo 1.2.0 supplies no resolver API, resolver discovery,
or portable implementation. Such code would need to recreate OS resolver
configuration and DNS behavior, and would not cover Windows. It is not a
production-safe, all-target DNS path under the current project rules.

The standard library cannot provide production WSS under these constraints.
There is no public TCP/TLS stream, certificate validation, TLS protocol,
cryptographic digest/cipher suite, or cryptographically secure random source.
The private socket layer alone cannot establish WSS. Implementing TLS and its
cryptographic dependencies from scratch in Mojo would be a new, unverified
security implementation, not a standard-library-supported production path.

## Reproducible probes

The probes used Mojo 1.2.0 (`2016d0cd`):

```sh
mojo build probes/gaps/network.mojo
mojo build probes/gaps/dns.mojo
mojo build probes/gaps/crypto.mojo
mojo run probes/gaps/network_platform.mojo
```

The public network probe fails with these import diagnostics:

```text
error: package 'net' does not contain 'TcpListener'
error: package 'net' does not contain 'TcpStream'
error: package 'net' does not contain 'TlsStream'
```

The DNS probe fails because `std.net` does not contain `getaddrinfo` or
`getnameinfo`:

```text
error: package 'net' does not contain 'getaddrinfo'
error: package 'net' does not contain 'getnameinfo'
```

The crypto probe fails because `std.hash` has no `SHA256` and `std.random` has
no `secure_random_bytes`:

```text
error: package 'hash' does not contain 'SHA256'
error: package 'random' does not contain 'secure_random_bytes'
```

The private socket probe creates and closes one local UDP socket and
instantiates the POSIX IPv4 address layout; it sends no network traffic. Its
local output is `16 53`.

The address-layout probe emits LLVM IR for the six frozen release target
triples with:

```sh
mojo build --target-triple TARGET --emit=llvm -o /tmp/network-TARGET.ll probes/gaps/network_platform.mojo
```

This compiles for `x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`,
`x86_64-apple-darwin`, and `aarch64-apple-darwin`. Both Windows targets,
`x86_64-pc-windows-msvc` and `aarch64-pc-windows-msvc`, fail when the `sockaddr_in`
layout is instantiated:

```text
error: struct 'std::sys::info::_UnsupportedTarget' does not have witness table for trait 'std::net::_sys::inet::SockaddrIn'
```

LLVM emission is a compile check only. It does not establish target linking,
runtime behavior, TLS, DNS, or release qualification on any target.

## References

- [Mojo `std.net`](https://mojolang.org/docs/std/net/): public networking types are not yet available.
- [Mojo `std.ffi`](https://mojolang.org/docs/std/ffi/): C FFI and dynamic library APIs.
- [Mojo `std.random`](https://mojolang.org/docs/std/random/): random APIs are not cryptographically secure.
- [Mojo `std.hash`](https://mojolang.org/docs/std/hash/): hashing interfaces and package modules.

The runtime-proxy transport requirements and current Modex implementation gaps
remain in `docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.
