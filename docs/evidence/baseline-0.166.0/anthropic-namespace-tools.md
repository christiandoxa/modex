# Anthropic namespace tools

The native Anthropic preflight now passes namespace tools to the shared
Responses mapper, which validates and flattens their function entries before
any provider request. Previously the preflight rejected them outright.

The active 0.166.0 process comparison in
`tests/test_anthropic_missing_message_content_01660.py` checks a namespace
function combined with web search in automatic and forced Anthropic modes.
Both products send the same synthetic provider body. Four malformed children
(non-string description, non-boolean strict flag, missing name and unsupported
type) produce matching 502 response bodies without a provider POST. The test
passed on Linux x86-64 in a user, mount and network namespace with private
temporary storage, isolated home, loopback only and no default routes. This
does not establish general Anthropic or Codex parity.
