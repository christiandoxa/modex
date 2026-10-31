# Buffered provider metadata

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The Linux oracle is verified by
SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`test_provider_metadata_01660.py` compares both real processes with synthetic
buffered responses and a loopback provider. Four cases exercise first-choice
selection, empty and whitespace strings, annotations, and nested request
metadata collisions. The test checks exact response metadata, normalized
responses, provider request bodies, and a single synthetic-key request.

The historical 0.439.2 source test
`mojo_chat_metadata_preserves_type_presence_and_first_choice` expects a
whitespace-only `reasoning_content` field to survive. The active 0.166.0
process and Modex both omit it in the tested case. No 0.439.2 process result is
claimed here. These selected cases do not establish complete metadata parity.
