"""Read-only installation prerequisite checks for doctor --install."""

from std.collections import List, Span
from std.os import getenv

from .log_redaction import redact_log_text
from .paths import app_root, shared_root
from .process_spawn import CapturedProcessOutput, capture_with_env
from .sessions import escape_terminal_controls
from .super_launch import (
    _dry_run_probe_environment,
    _executable_path,
    _is_legacy_codex,
    _is_prodex_wrapper,
    _managed_tool_present,
    _node_major_supported,
    _optional_tool_version_status,
    _path_candidates,
)
from .text import trim_text, unsigned_value, wrap_text
from .unicode_width import text_width


def _command_override(variable: String, fallback: String) -> String:
    var configured = getenv(variable, "\0")
    return fallback if configured == "\0" else configured


def _doctor_resolve(command: String) -> String:
    if "/" in command:
        return _executable_path(command)
    for candidate in _path_candidates(command, getenv("PATH", "\0")):
        var resolved = _executable_path(candidate)
        if resolved:
            return resolved^
    return String()


def _doctor_codex_command() -> Tuple[String, String]:
    var configured = getenv("PRODEX_CODEX_BIN", "\0")
    if configured != "\0":
        var resolved = _doctor_resolve(configured)
        if resolved and _is_prodex_wrapper(resolved):
            return (String(), "unavailable (configured Codex executable resolves to a Prodex wrapper; it was not run)")
        if resolved and _is_legacy_codex(resolved):
            return (String(), "unavailable (configured Codex executable is the legacy Prodex runtime; it was not run)")
        return (configured, String())
    var skipped_wrapper = False
    var skipped_legacy = False
    for candidate in _path_candidates("codex", getenv("PATH", "\0")):
        var resolved = _executable_path(candidate)
        if not resolved:
            continue
        if _is_prodex_wrapper(resolved):
            skipped_wrapper = True
            continue
        if _is_legacy_codex(resolved):
            skipped_legacy = True
            continue
        return (resolved, String())
    if skipped_wrapper and skipped_legacy:
        return (String(), "unavailable (PATH contains only Prodex wrapper and legacy runtime candidates; none were run)")
    if skipped_wrapper:
        return (String(), "unavailable (PATH contains only a Prodex wrapper; it was not run)")
    if skipped_legacy:
        return (String(), "unavailable (PATH contains only the legacy Prodex runtime; it was not run)")
    return (String("codex"), String())


def _doctor_exit_status(output: CapturedProcessOutput) -> String:
    if output.status.exit_code:
        return "exit status: " + String(output.status.exit_code.value())
    if output.status.term_signal:
        return "signal: " + String(output.status.term_signal.value())
    return "unknown process status"


def _doctor_probe_environment(include_codex_home: Bool) -> List[String]:
    var environment = _dry_run_probe_environment()
    for name in [
        String("USERPROFILE"),
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
    ]:
        var value = getenv(name, "\0")
        if value != "\0":
            environment.append(name + "=" + value)
    if include_codex_home:
        var codex_home = getenv("CODEX_HOME", "\0")
        if codex_home != "\0":
            environment.append("CODEX_HOME=" + codex_home)
    return environment^


def _doctor_first_line(bytes: List[UInt8]) -> String:
    var output = String(from_utf8_lossy=Span(bytes))
    for line in output.split("\n"):
        var trimmed = trim_text(line)
        if trimmed:
            return escape_terminal_controls(redact_log_text(trimmed))
    return String()


def _doctor_probe(command: String, args: List[String], success: String = "", include_codex_home: Bool = False) -> String:
    var binary = _doctor_resolve(command)
    if not binary:
        return "missing (" + escape_terminal_controls(redact_log_text("failed to start " + command)) + ")"
    var output: CapturedProcessOutput
    try:
        output = capture_with_env(
            binary,
            args,
            _doctor_probe_environment(include_codex_home),
            command,
            15000,
            1048576,
            argv0=command,
        )
    except error:
        var message = String(error)
        if message.find("process spawn failed with errno") >= 0:
            message = "failed to start " + command
        return "missing (" + escape_terminal_controls(redact_log_text(message)) + ")"
    if not output.status.exit_code or output.status.exit_code.value() != 0:
        return "warn (exit " + _doctor_exit_status(output) + ")"
    if success:
        return success
    var line = _doctor_first_line(output.stdout)
    if not line:
        line = _doctor_first_line(output.stderr)
    if not line:
        line = "available"
    return "ok (" + line + ")"


def _doctor_version_row(name: String, command: String) -> Tuple[String, String]:
    return (name, _doctor_probe(command, [String("--version")]))


def _doctor_optional_command_status(command: String, args: List[String]) -> String:
    if not _doctor_resolve(command):
        return "missing"
    return _doctor_probe(command, args)


def _doctor_node_supports_playwright() -> Bool:
    var node = _doctor_resolve("node")
    if not node:
        return False
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(
            node, [String("--version")], _doctor_probe_environment(False),
            "Node.js health check", 5000, 65536, argv0="node",
        )
    except:
        return False
    if not probe.status.exit_code or probe.status.exit_code.value() != 0:
        return False
    try:
        _ = String(from_utf8=Span(probe.stdout))
        _ = String(from_utf8=Span(probe.stderr))
    except:
        return False
    var version = _doctor_first_line(probe.stdout)
    if not version:
        version = _doctor_first_line(probe.stderr)
    return _node_major_supported(version)


def _doctor_playwright_status() -> String:
    if not _doctor_node_supports_playwright():
        return "missing"
    var npx = _doctor_resolve("npx")
    if not npx:
        return "missing"
    # --no-install keeps this diagnostic from fetching a package.
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(
            npx,
            [String("--no-install"), "@playwright/mcp", "--version"],
            _doctor_probe_environment(False),
            "playwright-mcp health check",
            5000,
            65536,
            argv0="npx",
        )
    except:
        return "missing"
    if not probe.status.exit_code or probe.status.exit_code.value() != 0:
        return "missing"
    try:
        _ = String(from_utf8=Span(probe.stdout))
        _ = String(from_utf8=Span(probe.stderr))
    except:
        return "missing"
    var line = _doctor_first_line(probe.stdout)
    if not line:
        line = _doctor_first_line(probe.stderr)
    if not line:
        return "missing"
    var version_status = _optional_tool_version_status(line, False)
    if not version_status.startswith("resolved "):
        return version_status if version_status else "missing (unrecognized Playwright MCP version)"
    return "ok (" + line + ")"


def _doctor_ponytail_status() -> String:
    if _managed_tool_present("ponytail"):
        # shortcut: report presence only; add plugin-tree validation before claiming installed.
        return "degraded (managed Ponytail found; plugin-tree validation is unavailable)"
    return String("missing")


def _doctor_terminal_width() -> Int:
    var configured = getenv("PRODEX_TERM_COLUMNS", "\0")
    if configured != "\0":
        try:
            var parsed = unsigned_value(configured)
            if parsed > 0 and parsed <= 4096:
                return Int(parsed)
        except:
            pass
    return 120


def _doctor_repeat(value: String, count: Int) -> String:
    var output = String()
    for _ in range(count):
        output += value
    return output


def _print_doctor_install_panel(fields: List[Tuple[String, String]]) raises:
    var width = _doctor_terminal_width()
    var header_prefix = String("[ Install Checks ] ")
    if text_width(header_prefix) < width:
        print(header_prefix + _doctor_repeat("=", width - text_width(header_prefix)))
    else:
        print(wrap_text(header_prefix, width)[0])

    var label_width = 10
    for field in fields:
        label_width = max(label_width, text_width(field[0] + ":"))
    label_width = min(label_width, 24)
    if width > 2:
        label_width = min(label_width, width - 2)
    var value_width = max(1, width - label_width - 1)
    for field in fields:
        var label = field[0] + ":"
        var rows = wrap_text(field[1], value_width)
        for index in range(len(rows)):
            var rendered_label = label if index == 0 else String()
            var padding = label_width - text_width(rendered_label) if index == 0 else label_width
            print(rendered_label + _doctor_repeat(" ", max(0, padding)) + " " + rows[index])


def run_doctor_install() raises:
    var rows = List[Tuple[String, String]]()
    var codex, codex_unavailable = _doctor_codex_command()
    if codex_unavailable:
        rows.append(("Codex CLI", codex_unavailable))
        rows.append(("Codex auth", "skipped (unsafe Codex executable was not run)"))
    else:
        rows.append(("Codex CLI", _doctor_probe(codex, [String("--version")], include_codex_home=True)))
        rows.append(("Codex auth", _doctor_probe(codex, [String("login"), "status"], "ok", include_codex_home=True)))
    rows.append(_doctor_version_row("Claude Code", _command_override("PRODEX_CLAUDE_BIN", "claude")))
    rows.append(_doctor_version_row("Gemini CLI", _command_override("PRODEX_GEMINI_BIN", "gemini")))
    rows.append(_doctor_version_row("GitHub Copilot CLI", _command_override("PRODEX_COPILOT_BIN", "copilot")))

    var kiro = getenv("PRODEX_KIRO_BIN", "\0")
    if kiro == "\0":
        kiro = "kiro-cli-chat"
        if not _doctor_resolve(kiro) and _doctor_resolve("kiro-cli"):
            kiro = "kiro-cli"
    rows.append(_doctor_version_row("Kiro CLI", kiro))

    rows.append(_doctor_version_row("Antigravity CLI", _command_override("PRODEX_AGY_BIN", "agy")))
    rows.append(_doctor_version_row("Node.js", "node"))
    rows.append(_doctor_version_row("npx", "npx"))
    rows.append(("rtk", _doctor_optional_command_status("rtk", [String("--version")])))
    rows.append(("codebase-memory-mcp", _doctor_optional_command_status("codebase-memory-mcp", [String("--version")])))
    rows.append(("playwright-mcp", _doctor_playwright_status()))
    rows.append(("ponytail", _doctor_ponytail_status()))

    var root = app_root()
    rows.append(("Prodex home", escape_terminal_controls(redact_log_text(root))))
    rows.append(("Shared CODEX_HOME", escape_terminal_controls(redact_log_text(shared_root(root)))))
    _print_doctor_install_panel(rows)
