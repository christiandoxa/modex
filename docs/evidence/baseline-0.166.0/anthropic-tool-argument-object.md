# Anthropic tool-history argument validation

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

On mixed web-search and function-call history, the reference rejects valid JSON
arguments that are arrays, strings, numbers, booleans, or null with HTTP 400
before the Anthropic provider is contacted. Modex previously forwarded those
values. Its Anthropic translator now checks the decoded JSON type, preserving
the existing malformed-JSON rejection and routing the new error through the
same incompatible-request response. The separate OpenAI Chat path continues
to accept the selected non-object and malformed-string controls like the
release.

The pinned `mojo/prodex_core/anthropic_chat_messages.mojo` validates tool-call
argument JSON and requires an object. The active process regression compares
both products in `auto` and `anthropic` search modes for five non-object JSON
types, malformed JSON and an object control, plus two `openai_chat` controls.
It asserts status, error bytes or provider request body, destination path, and
absence of an upstream request on rejection. The custom-tool and provider-shape
modules passed eight tests in a private loopback-only network namespace using
synthetic credentials and isolated temporary state. This covers selected Linux
x86-64 request shapes; other provider behavior and release targets remain open.
