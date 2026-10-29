"""Native clean-home DeepSeek exec launch and direct-child ownership."""

from std.collections import List, Optional, Span
from std.io import RawFileDescriptor
from std.net._sys.unix import F_GETFL, F_SETFL, O_NONBLOCK
from std.os import getenv, getuid, isatty, listdir, lstat, mkdir, remove, rmdir, symlink
from std.os.path import exists, lexists, realpath
from std.os.process import Pipe, Process, ProcessStatus
from std.pathlib import cwd
from std.sys._libc import fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.sys import stderr
from std.time import perf_counter, sleep

from .app_server_rpc import run_super_hook_trust_preflight
from .json import quote_json
from .loopback_server import LoopbackHTTPListener
from .paths import app_root, ensure_app_root, shared_root
from .process_spawn import CapturedProcessOutput, capture_with_env, inherited_environment, spawn_with_env, spawn_with_env_stdio, terminate_child_gracefully, wait_or_kill
from .provider_deepseek_transport import deepseek_request_headers
from .runtime_local_rewrite import deepseek_runtime_route, local_rewrite_upstream, serve_local_rewrite
from .sessions import read_private_state_file
from .sha256 import hash_file
from .text import cli_width, is_whitespace, section_header, trim_text, wrap_text
from .toml import TOMLDocument, TOML_STRING, TOML_TABLE
from .uuid7 import new_uuid7

comptime CODEX_INSTALL_GUIDANCE = String(
    "Install or update the official Codex CLI with `npm install -g @openai/codex@latest` "
    + "(https://developers.openai.com/codex/cli), verify `codex --version`, or set "
    + "PRODEX_CODEX_BIN to its executable path. Prodex accepts compatible Codex releases "
    + "at or above its minimum capability baseline; the latest stable release is recommended."
)


def _private_directory(path: String) raises:
    if not lexists(path):
        mkdir(path, 0o700)
    var info = lstat(path)
    if info.st_mode & 0o170000 != 0o040000 or info.st_uid != getuid() or info.st_mode & 0o077:
        raise Error("Super launch requires an owned private directory")


def _remove_overlay(path: String) raises:
    # Preserve unknown Codex state until its shared-storage lifecycle is implemented.
    for name in listdir(path):
        if name not in ["auth.json", "config.toml", "prodex-deepseek-model-catalog.json", "history.jsonl", "sessions", "archived_sessions", "attachments", "image_attachments"]:
            print("Modex retained Codex runtime data in " + path, file=stderr)
            return
        if name in ["history.jsonl", "sessions", "archived_sessions", "attachments", "image_attachments"] and lstat(path + "/" + name).st_mode & 0o170000 != 0o120000:
            print("Modex retained Codex runtime data in " + path, file=stderr)
            return
    for name in listdir(path):
        remove(path + "/" + name)
    rmdir(path)


def _clean_home(root: String, shared: String) raises -> Tuple[String, Optional[String]]:
    # shortcut: existing profile/config reconciliation needs locked storage; admit only a web-search-only config and no saved account state.
    var config_source = String()
    var search_mode = Optional[String]()
    if lexists(shared):
        var info = lstat(shared)
        if info.st_mode & 0o170000 != 0o040000 or info.st_uid != getuid() or info.st_mode & 0o077:
            raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
        for name in listdir(shared):
            if name != "config.toml":
                raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
            var path = shared + "/config.toml"
            if lstat(path).st_size > 1048576:
                raise Error("Super Codex config exceeds the supported size")
            var bytes = read_private_state_file(path)
            if len(bytes) > 1048576:
                raise Error("Super Codex config exceeds the supported size")
            config_source = String(from_utf8=Span(bytes))
            var config = TOMLDocument(config_source)
            var deepseek = config.get(config.root, "deepseek")
            if len(config.nodes[config.root].names) != 1 or deepseek < 0 or config.nodes[deepseek].kind != TOML_TABLE or len(config.nodes[deepseek].names) != 1:
                raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
            var node = config.get(deepseek, "web_search_mode")
            if node < 0:
                raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
            if config.nodes[node].kind != TOML_STRING:
                raise Error("deepseek.web_search_mode must be a string")
            search_mode = Optional[String](config.string(node))
    if lexists(root):
        for name in listdir(root):
            if name != "update-check.json" and name != "profiles":
                raise Error("Super clean-home launch cannot reconcile existing application state yet")
            if name == "profiles" and (lstat(root + "/profiles").st_mode & 0o170000 != 0o040000 or listdir(root + "/profiles")):
                raise Error("Super clean-home launch requires an empty profiles directory")
    return config_source^, search_mode^


def _ascii_lower(value: String) -> String:
    var result = String()
    for character in value.codepoints():
        var code = Int(character)
        result += chr(code + 32 if 65 <= code <= 90 else code)
    return result


def _path_candidates(command: String, path: String) -> List[String]:
    var candidates = List[String]()
    if path == "\0":
        return candidates^
    for directory in path.split(":"):
        var candidate = String(directory)
        if candidate and not candidate.endswith("/"):
            candidate += "/"
        candidates.append(candidate + command)
    return candidates^


def _executable_path(candidate: String) -> String:
    try:
        var resolved = realpath(candidate)
        var info = lstat(resolved)
        if info.st_mode & 0o170000 != 0o100000 or info.st_mode & 0o111 == 0:
            return String()
        return resolved^
    except:
        return String()


def _is_prodex_wrapper(path: String) -> Bool:
    var parts = path.split("/")
    var basename = _ascii_lower(String(parts[len(parts) - 1]))
    if basename == "prodex" or basename == "prodex.exe":
        return True
    try:
        if realpath("/proc/self/exe") == path:
            return True
    except:
        pass
    var bytes: List[UInt8]
    try:
        with open(path, "r") as file:
            bytes = file.read_bytes(8192)
    except:
        return False
    for byte in bytes:
        if byte == 0:
            return False
    var source: String
    try:
        source = String(from_utf8=Span(bytes))
    except:
        return False
    var lowered = _ascii_lower(source)
    if lowered.find("codex-shim") >= 0 or lowered.find("@christiandoxa/prodex") >= 0:
        return True
    for line in source.split("\n"):
        var normalized = _ascii_lower(trim_text(line))
        if (normalized.startswith("exec ") or normalized.find("spawn") >= 0) and normalized.find("prodex") >= 0:
            return True
    return False


def _is_legacy_codex(path: String) -> Bool:
    var digest: String
    try:
        digest = hash_file(path, Int.MAX)
    except:
        return False
    return digest in [
        "31b366ac32f41988056f56ce299d84489b90a18623fa8419dcfd2d39065dd252",
        "61303e421811460cc8f5a86d765c5b2bbc1578ef8ff606103ef22da0fd74de05",
        "7990011a697152a285b8511705572400756febac2fbd5d9d8219a876019ed0b7",
        "e73621dc0acad757636a5ac81d40c727f0a3f055af3ddaab8861aeaf2ba2fa61",
        "f45c814867246310abf3dfdfc1e8f0e95123b096ef3bcd089562694fe05f2497",
        "9f5a4e4fbbd784a18e4a46f977aaeb957510e4f6e1b97ef9a31091151b42df71",
    ]


def _codex_binary() raises -> Tuple[String, String, String]:
    var requested = getenv("PRODEX_CODEX_BIN", "\0")
    var path = getenv("PATH", "\0")
    var configured = requested != "\0"
    if not configured:
        for candidate in _path_candidates("codex", path):
            var resolved = _executable_path(candidate)
            if not resolved or _is_prodex_wrapper(resolved) or _is_legacy_codex(resolved):
                continue
            return (resolved, resolved, resolved)
        requested = "codex"

    var resolved = String()
    var child_path = requested
    if requested.find("/") >= 0:
        resolved = _executable_path(requested)
    else:
        for candidate in _path_candidates(requested, path):
            resolved = _executable_path(candidate)
            if resolved:
                child_path = candidate
                break
    if not resolved:
        raise Error("Codex CLI is unavailable. " + CODEX_INSTALL_GUIDANCE)
    if _is_prodex_wrapper(resolved):
        raise Error("Codex executable resolves to a Prodex wrapper: " + resolved + ". " + CODEX_INSTALL_GUIDANCE)
    if _is_legacy_codex(resolved):
        raise Error(
            "Codex executable " + resolved + " is the legacy Prodex-bundled runtime from 0.426.1. "
            + "It was left untouched, but Prodex 0.427.0 will not run it. " + CODEX_INSTALL_GUIDANCE
        )
    return (resolved, child_path, requested)


def deepseek_model_catalog(launch_model: String) -> String:
    var presets: List[Tuple[String, String, String]] = [
        ("auto", "DeepSeek Auto", "Prodex DeepSeek fallback chain routed through current DeepSeek models."),
        ("pro", "DeepSeek Pro", "Prodex DeepSeek Pro alias routed through DeepSeek V4 Pro."),
        ("flash", "DeepSeek Flash", "Prodex DeepSeek Flash alias routed through DeepSeek V4 Flash."),
        ("deepseek-v4-pro", "DeepSeek V4 Pro", "DeepSeek V4 Pro routed through the Prodex Responses adapter."),
        ("deepseek-v4-flash", "DeepSeek V4 Flash", "DeepSeek V4 Flash routed through the Prodex Responses adapter."),
        ("deepseek-chat", "DeepSeek Chat", "DeepSeek chat compatibility model routed through the Prodex Responses adapter."),
        ("deepseek-reasoner", "DeepSeek Reasoner", "DeepSeek reasoner compatibility model routed through the Prodex Responses adapter."),
    ]
    var instructions = String("You are Codex, a coding agent. You and the user share the same workspace.\n\nFocus on the user's software task. Inspect the codebase before changing behavior, make narrow edits, preserve user changes, and verify with relevant tests or commands when feasible.\n\nUse tools deliberately. For shell work, prefer fast focused commands. For file edits, keep changes minimal and explain non-obvious logic in short comments only when useful.")
    var models = List[String]()
    var slugs: List[String] = [launch_model]
    for preset in presets:
        slugs.append(preset[0])
    var seen = List[String]()
    for slug in slugs:
        var folded = _ascii_lower(slug)
        if folded in seen:
            continue
        seen.append(folded)
        var name = slug
        var description = String("DeepSeek model routed through the Prodex Responses adapter.")
        for preset in presets:
            if preset[0] == folded:
                name = preset[1]
                description = preset[2]
                break
        var row = String('{"additional_speed_tiers":[],"apply_patch_tool_type":"freeform","auto_compact_token_limit":900000,"availability_nux":null,"base_instructions":') + quote_json(instructions)
        row += ',"context_window":1048576,"default_reasoning_level":"high","default_reasoning_summary":"none","default_service_tier":null,"default_verbosity":null,"description":' + quote_json(description)
        row += ',"display_name":' + quote_json(name) + ',"effective_context_window_percent":95,"experimental_supported_tools":[],"input_modalities":["text"],"max_context_window":1048576,"priority":' + String(len(models) + 1)
        row += ',"service_tiers":[],"shell_type":"shell_command","slug":' + quote_json(slug) + ',"support_verbosity":false,"supported_in_api":true,"supported_reasoning_levels":['
        row += '{"description":"DeepSeek low reasoning effort","effort":"low"},{"description":"DeepSeek medium reasoning effort","effort":"medium"},{"description":"DeepSeek high reasoning effort","effort":"high"},{"description":"DeepSeek max reasoning effort","effort":"xhigh"}]'
        row += ',"supports_image_detail_original":false,"supports_parallel_tool_calls":true,"supports_reasoning_summaries":false,"supports_reasoning_summary_parameter":false,"supports_search_tool":false,"truncation_policy":{"limit":10000,"mode":"tokens"},"upgrade":null,"visibility":"list","web_search_tool_type":"text"}'
        models.append(row)
    return '{"models":[' + String(",").join(models) + "]}"


def _child_environment(home: String) -> List[String]:
    var excluded: List[String] = ["CODEX_HOME", "CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT", "NO_PROXY", "no_proxy", "LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "LD_ORIGIN_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "PRODEX_RUNTIME_LOCAL_UPSTREAM", "PRODEX_RUNTIME_LOCAL_KEY", "PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE"]
    var environment = inherited_environment(excluded)
    var clean = List[String]()
    for entry in environment:
        var name = String(entry.split("=", maxsplit=1)[0])
        if not name.startswith("CODEX_SANDBOX") and not name.startswith("DYLD_"):
            clean.append(entry)
    clean.append("CODEX_HOME=" + home)
    clean.append("CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT=1")
    var bypass = List[String]()
    for source in [getenv("NO_PROXY"), getenv("no_proxy"), String("127.0.0.1,localhost,::1")]:
        for part in source.split(","):
            var value = String(part.strip())
            var duplicate = False
            for previous in bypass:
                duplicate = duplicate or _ascii_lower(previous) == _ascii_lower(value)
            if value and not duplicate:
                bypass.append(value)
    var merged = String(",").join(bypass)
    clean.append("NO_PROXY=" + merged)
    clean.append("no_proxy=" + merged)
    return clean^


def _codex_probe_environment(environment: List[String]) -> List[String]:
    var removed: List[String] = [
        "CODEX_HOME=", "TEST_CODEX_LOG=", "TEST_CODEX_LOG_APPEND=",
        "TEST_CODEX_ARGS_LOG=", "TEST_CODEX_ARGS_LOG_APPEND=", "TEST_CODEX_STDIN_LOG=",
    ]
    var result = List[String]()
    for entry in environment:
        var should_remove = False
        for prefix in removed:
            should_remove = should_remove or entry.startswith(prefix)
        if not should_remove:
            result.append(entry)
    return result^


def _child_exit_code(status: ProcessStatus) -> Int:
    if status.exit_code:
        return status.exit_code.value()
    if status.term_signal:
        return 128 + status.term_signal.value()
    return 1


def run_local_rewrite_child() raises:
    """Private self-process entrypoint; credentials stay out of argv and output."""
    var upstream = getenv("PRODEX_RUNTIME_LOCAL_UPSTREAM")
    var key = getenv("PRODEX_RUNTIME_LOCAL_KEY")
    _ = local_rewrite_upstream(upstream)
    _ = deepseek_request_headers([], key)
    var configured_mode = getenv("PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE", "\x00")
    var route = deepseek_runtime_route(Optional[String](configured_mode) if configured_mode != "\x00" else None)
    var listener = LoopbackHTTPListener("127.0.0.1:0")
    var output = RawFileDescriptor(1)
    output.write_bytes((listener.address + "\n").as_bytes())
    serve_local_rewrite(listener, upstream, key, route[0], route[1], route[2], parent_fd=0, allow_local_file_access=True, web_search_mode=route[3])


def _ready(input_pipe: Pipe, mut child: Process) raises -> String:
    var fd = input_pipe.fd_in.value().value
    var flags = fcntl(fd, F_GETFL, 0)
    if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
        raise Error("could not configure local provider readiness channel")
    var buffer = List[UInt8](length=256, fill=0)
    var used = 0
    var deadline = perf_counter() + 5.0
    while perf_counter() < deadline:
        var input = RawFileDescriptor(fd)
        var count: Int
        try:
            count = input.read_bytes(Span(buffer)[used:])
        except:
            var error = get_errno()
            if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                raise Error("local provider readiness channel failed")
            if child.poll().has_exited():
                raise Error("local provider exited during startup")
            sleep(0.001)
            continue
        if count == 0:
            raise Error("local provider closed its readiness channel")
        used += count
        if buffer[used - 1] == 10:
            var address = String(from_utf8=Span(buffer)[:used - 1])
            _ = local_rewrite_upstream("http://" + address + "/v1")
            return address
        if used == len(buffer):
            raise Error("local provider readiness address is too large")
    raise Error("local provider startup timed out")


def _config(mut args: List[String], key: String, value: String):
    args.append("-c")
    args.append(key + "=" + value)


# TOML permits literal TAB here, matching the pinned model override spelling.
def _toml_model_literal(value: String) -> String:
    var encoded = quote_json(value)
    var result = String()
    var escaped = False
    for character in encoded.codepoints():
        var code = Int(character)
        if escaped:
            result += chr(9) if code == 116 else "\\" + chr(code)
            escaped = False
        elif code == 92:
            escaped = True
        elif code == 127:
            result += "\\u007f"
        else:
            result += chr(code)
    return result


def _truthy_environment_value(value: String) -> Bool:
    var normalized = _ascii_lower(trim_text(value))
    return normalized == "1" or normalized == "true" or normalized == "yes"


def _launch_progress_fallback() -> Bool:
    # Interactive launch progress uses a live terminal panel, which Modex does not render yet.
    if not isatty(2) or getenv("CODEX_CI", "\0") != "\0":
        return True
    return getenv("TERM", "") == "dumb" or _truthy_environment_value(getenv("PRODEX_TUI_STRICT", ""))


def _print_fallback_stderr_panel(title: String, message: String) raises:
    var width = cli_width()
    print(section_header(title, width), file=stderr)
    for line in wrap_text(message, width):
        print(line, file=stderr)


def _deepseek_launch_progress() raises:
    if not _launch_progress_fallback():
        return
    var messages = [
        String("preparing runtime launch..."),
        String("Smart Context runtime proxy requested."),
        String("local provider bridge requested."),
    ]
    if isatty(2) and getenv("CODEX_CI", "\0") == "\0":
        for message in messages:
            _print_fallback_stderr_panel("Prodex Launch", message)
    else:
        for message in messages:
            print("Prodex launch: " + message, file=stderr)


def _deepseek_provider_panel() raises:
    if not _launch_progress_fallback():
        return
    _print_fallback_stderr_panel(
        "Runtime Provider",
        "Using provider 'deepseek' through the local compatibility proxy. Smart Context rewrites require a proven tokenizer. Using one provider API key; API-key rotation is skipped and quota preflight stays disabled.",
    )


def _capture_codex_probe(binary: String, args: List[String], environment: List[String], label: String) raises -> CapturedProcessOutput:
    try:
        return capture_with_env(binary, args, environment, label, argv0=binary)
    except error:
        raise Error("failed to probe Codex CLI at " + binary + ": " + String(error))


def _codex_probe_version(output: String) -> String:
    # The release chooses the rightmost whitespace-delimited version-like token.
    var token = String()
    var candidate = String()
    var starts_with_digit = False
    var has_dot = False
    var last_kept = 0
    for character in output.codepoints():
        var code = Int(character)
        if is_whitespace(code):
            if starts_with_digit and has_dot:
                candidate = String(token[byte=0:last_kept])
            token = ""
            starts_with_digit = False
            has_dot = False
            last_kept = 0
            continue
        if not token:
            starts_with_digit = 48 <= code <= 57
        token += chr(code)
        if code == 46:
            has_dot = True
        if 48 <= code <= 57 or 65 <= code <= 90 or 97 <= code <= 122 or code == 45 or code == 46:
            last_kept = token.byte_length()
    if starts_with_digit and has_dot:
        candidate = String(token[byte=0:last_kept])
    return candidate


def _codex_version_parts(value: String) -> List[UInt64]:
    var parts = List[UInt64]()
    var number = UInt64(0)
    var digits = 0
    var component_start = True
    for character in value.codepoints():
        var code = Int(character)
        if 48 <= code <= 57:
            var digit = UInt64(code - 48)
            if number > (UInt64.MAX - digit) // 10:
                return parts^
            number = number * 10 + digit
            digits += 1
            component_start = False
        elif code == 46:
            if digits == 0 or len(parts) == 2:
                return parts^
            parts.append(number)
            number = 0
            digits = 0
            component_start = True
        elif code == 43 and component_start:
            # Rust's unsigned parser permits one leading plus per component.
            component_start = False
        else:
            return parts^
    if digits == 0 or len(parts) != 2:
        return parts^
    parts.append(number)
    return parts^


def _exec(binary: String, child_path: String, argv0: String, home: String, model: String, upstream: String, key: String, prompt: List[String], context_window: UInt64, compact_limit: UInt64, web_search_mode: String) raises -> Int:
    var environment = _child_environment(home)
    var probe_environment = _codex_probe_environment(environment)
    var version = _capture_codex_probe(binary, [String("--version")], probe_environment, "Codex version probe")
    if not version.status.exit_code or version.status.exit_code.value() != 0:
        raise Error(
            "Codex version probe failed for " + binary + " with status "
            + String(_child_exit_code(version.status)) + ". " + CODEX_INSTALL_GUIDANCE
        )
    var version_output = String(from_utf8_lossy=Span(version.stdout)) + "\n" + String(from_utf8_lossy=Span(version.stderr))
    if _ascii_lower(version_output).find("codex") < 0:
        raise Error("Codex CLI at " + binary + " did not report a recognizable version. " + CODEX_INSTALL_GUIDANCE)
    var reported_version = _codex_probe_version(version_output)
    var parts = _codex_version_parts(reported_version)
    if len(parts) != 3:
        raise Error("Codex CLI at " + binary + " did not report a recognizable version. " + CODEX_INSTALL_GUIDANCE)
    if parts[0] == UInt64(0) and (parts[1] < UInt64(153) or (parts[1] == UInt64(153) and parts[2] < UInt64(2))):
        raise Error(
            "Codex CLI at " + binary + " reports " + String(parts[0]) + "." + String(parts[1]) + "." + String(parts[2])
            + "; Prodex requires 0.153.2 or newer. " + CODEX_INSTALL_GUIDANCE
        )
    var capability = _capture_codex_probe(binary, [String("app-server"), String("--help")], probe_environment, "Codex app-server capability probe")
    if not capability.status.exit_code or capability.status.exit_code.value() != 0:
        raise Error(
            "Codex app-server capability probe failed for " + binary + " with status "
            + String(_child_exit_code(capability.status)) + ". " + CODEX_INSTALL_GUIDANCE
        )
    var input = Pipe()
    var output = Pipe()
    var relay_environment = _child_environment(home)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_UPSTREAM=" + upstream)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_KEY=" + key)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE=" + web_search_mode)
    var relay: Process
    with open("/dev/null", "w") as errors:
        relay = spawn_with_env_stdio(realpath("/proc/self/exe"), [String("__modex-local-rewrite")], relay_environment, input.fd_in.value().value, output.fd_out.value().value, RawFileDescriptor(errors).value)
    input.set_output_only()
    output.set_input_only()
    try:
        var address = _ready(output, relay)
        var args = List[String]()
        _config(args, "model_catalog_json", quote_json(home + "/prodex-deepseek-model-catalog.json"))
        _config(args, "projects", "{" + quote_json(String(cwd())) + "={trust_level=\"trusted\"}}")
        _config(args, "model_provider", "\"prodex-deepseek\"")
        _config(args, "model", _toml_model_literal(model))
        _config(args, "model_providers.prodex-deepseek.name", "\"DeepSeek\"")
        _config(args, "model_providers.prodex-deepseek.base_url", quote_json("http://" + address + "/v1"))
        _config(args, "model_providers.prodex-deepseek.wire_api", "\"responses\"")
        _config(args, "model_providers.prodex-deepseek.requires_openai_auth", "true")
        _config(args, "model_providers.prodex-deepseek.supports_websockets", "false")
        _config(args, "model_context_window", String(context_window))
        _config(args, "model_auto_compact_token_limit", String(compact_limit))
        _config(args, "model_reasoning_summary", "\"none\"")
        _config(args, "web_search", "\"live\"")
        for feature in [String("apps"), String("js_repl"), String("image_generation")]:
            _config(args, "features." + feature, "false")
        # shortcut: selected paths can be replaced after probing; use file-descriptor spawn when available.
        var allow_relative = not child_path.startswith("/")
        var legacy = run_super_hook_trust_preflight(child_path, String(cwd()), args, environment, argv0, allow_relative)
        var launch = List[String]()
        if legacy:
            launch.append("--dangerously-bypass-hook-trust")
        launch.append("--dangerously-bypass-approvals-and-sandbox")
        launch.append("exec")
        launch.extend(args^)
        launch.extend(prompt.copy())
        if _launch_progress_fallback():
            print("Prodex launch: starting child process...", file=stderr)
        var child = spawn_with_env(child_path, launch, environment, argv0, allow_relative)
        var result: ProcessStatus
        try:
            while not child.poll().has_exited():
                if relay.poll().has_exited():
                    raise Error("local provider exited while Codex was running")
                sleep(0.005)
            result = child.wait()
        except:
            _ = terminate_child_gracefully(child)
            raise
        _ = wait_or_kill(relay, 1)
        input.set_input_only()
        return result.exit_code.value() if result.exit_code else 1
    except:
        _ = wait_or_kill(relay, 1)
        input.set_input_only()
        raise


def run_clean_deepseek_super(model: String, upstream: String, key: String, prompt: List[String], context_window: UInt64 = 0, compact_limit: UInt64 = 0, profile: String = "", profile_supplied: Bool = False) raises -> Int:
    _deepseek_launch_progress()
    _ = local_rewrite_upstream(upstream)
    _ = deepseek_request_headers([], key)
    var launch_context = context_window if context_window > 1 else UInt64(1048576)
    var launch_compact = min(compact_limit if compact_limit > 0 else UInt64(900000), launch_context - 1)
    var launch_model = trim_text(model)
    if not launch_model:
        launch_model = "deepseek-v4-pro"
    var model_literal = quote_json(launch_model)
    # The frozen catalog's config scanner strips quotes without unescaping them.
    var catalog_model = trim_text(String(model_literal[byte=1:model_literal.byte_length() - 1]))
    if catalog_model.byte_length() > 4096:
        raise Error("DeepSeek model identifier exceeds 4096 bytes")
    var root = app_root()
    var shared = shared_root(root)
    var shared_config = _clean_home(root, shared)
    var route = deepseek_runtime_route(shared_config[1])
    if profile_supplied:
        raise Error("profile '" + profile + "' does not exist")
    _ = ensure_app_root()
    _private_directory(shared)
    _private_directory(root + "/profiles")
    _deepseek_provider_panel()
    var home = root + "/profiles/.prodex-overlay-" + new_uuid7()
    mkdir(home, 0o700)
    try:
        for name in [String("sessions"), String("archived_sessions"), String("attachments"), String("image_attachments")]:
            mkdir(shared + "/" + name, 0o700)
            symlink(shared + "/" + name, home + "/" + name)
        with open(shared + "/history.jsonl", "w") as history:
            history.write("")
        symlink(shared + "/history.jsonl", home + "/history.jsonl")
        with open(home + "/config.toml", "w") as config:
            config.write(shared_config[0])
        with open(home + "/auth.json", "w") as auth:
            auth.write("{\"OPENAI_API_KEY\":\"prodex-runtime-provider\",\"agent_identity\":null,\"auth_mode\":\"apikey\",\"last_refresh\":null,\"tokens\":null}")
        with open(home + "/prodex-deepseek-model-catalog.json", "w") as catalog:
            # Frozen exact-value lookup ignores numeric -c overrides when building the catalog.
            catalog.write(deepseek_model_catalog(catalog_model))
        var codex = _codex_binary()
        var result = _exec(codex[0], codex[1], codex[2], home, launch_model, upstream, key, prompt, launch_context, launch_compact, route[3])
        _remove_overlay(home)
        return result
    except:
        _remove_overlay(home)
        raise
