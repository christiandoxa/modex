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
from .json import JSON_ARRAY, JSON_STRING, JsonDocument, quote_json
from .log_redaction import redact_log_text
from .loopback_server import LoopbackHTTPListener
from .paths import app_root, ensure_app_root, shared_root
from .process_spawn import CapturedProcessOutput, capture_with_env, inherited_environment, spawn_with_env, spawn_with_env_stdio, terminate_child_gracefully, wait_or_kill
from .provider_deepseek_transport import deepseek_request_headers
from .runtime_local_rewrite import deepseek_runtime_route, local_rewrite_upstream, local_rewrite_worker_count, serve_local_rewrite
from .sessions import read_private_state_file
from .sha256 import hash_file
from .text import ascii_lower, cli_width, is_whitespace, section_header, trim_text, unsigned_value, wrap_text
from .toml import TOMLDocument, TOML_BOOLEAN, TOML_STRING, TOML_TABLE
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


def _clean_home(root: String, shared: String, skip_config: Bool = False, read_only: Bool = False) raises -> Tuple[String, Optional[String], Optional[String], Optional[String]]:
    # shortcut: live shared-session and profile updates need compatible locked storage.
    var config_source = String()
    var search_mode = Optional[String]()
    var strict_tools = Optional[String]()
    var beta_base_url = Optional[String]()
    if lexists(shared):
        var info = lstat(shared)
        if info.st_mode & 0o170000 != 0o040000 or info.st_uid != getuid() or info.st_mode & 0o077:
            raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
        for name in listdir(shared):
            if name != "config.toml":
                if read_only:
                    continue
                raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
            var path = shared + "/config.toml"
            if lstat(path).st_size > 1048576:
                raise Error("Super Codex config exceeds the supported size")
            var bytes = read_private_state_file(path)
            if len(bytes) > 1048576:
                raise Error("Super Codex config exceeds the supported size")
            config_source = String(from_utf8=Span(bytes))
            var config = TOMLDocument(config_source)
            if skip_config:
                continue
            var deepseek = config.get(config.root, "deepseek")
            if deepseek >= 0 and config.nodes[deepseek].kind == TOML_TABLE:
                var node = config.get(deepseek, "web_search_mode")
                if node >= 0:
                    if config.nodes[node].kind != TOML_STRING:
                        raise Error("deepseek.web_search_mode must be a string")
                    search_mode = Optional[String](config.string(node))
                node = config.get(deepseek, "strict_tools")
                if node >= 0:
                    if config.nodes[node].kind != TOML_STRING and config.nodes[node].kind != TOML_BOOLEAN:
                        raise Error("deepseek.strict_tools must be a boolean")
                    strict_tools = Optional[String](config.nodes[node].text)
                node = config.get(deepseek, "beta_base_url")
                if node >= 0 and config.nodes[node].kind == TOML_STRING:
                    var value = config.string(node)
                    if trim_text(value):
                        beta_base_url = Optional[String](value^)
    if lexists(root):
        for name in listdir(root):
            if name != "update-check.json" and name != "profiles":
                raise Error("Super clean-home launch cannot reconcile existing application state yet")
            if name == "profiles" and (lstat(root + "/profiles").st_mode & 0o170000 != 0o040000 or listdir(root + "/profiles")):
                raise Error("Super clean-home launch requires an empty profiles directory")
    return config_source^, search_mode^, strict_tools^, beta_base_url^


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
    var basename = ascii_lower(String(parts[len(parts) - 1]))
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
    var lowered = ascii_lower(source)
    if lowered.find("codex-shim") >= 0 or lowered.find("@christiandoxa/prodex") >= 0:
        return True
    for line in source.split("\n"):
        var normalized = ascii_lower(trim_text(line))
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


def _dry_run_codex_binary() -> String:
    var configured = getenv("PRODEX_CODEX_BIN", "\0")
    if configured != "\0":
        return configured^
    var path = getenv("PATH", "\0")
    if path and path != "\0":
        for candidate in _path_candidates("codex", path):
            var resolved = _executable_path(candidate)
            if not resolved or _is_prodex_wrapper(resolved) or _is_legacy_codex(resolved):
                continue
            return resolved^
    return "codex"


def _catalog_config_number(config: TOMLDocument, key: String, fallback: UInt64) raises -> UInt64:
    var node = config.get(config.root, key)
    if node < 0 or config.nodes[node].kind != TOML_STRING:
        return fallback
    var value = config.string(node)
    var name = "DeepSeek " + key
    if not value:
        raise Error(name + " cannot be empty")
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            raise Error(name + " must not contain whitespace")
    var parsed: UInt64
    try:
        parsed = unsigned_value(value)
    except error:
        raise Error(name + " must be an unsigned integer: " + String(error))
    if parsed <= 1:
        raise Error(name + " must be greater than 1")
    return parsed


def deepseek_model_catalog(launch_model: String, context_window: UInt64, compact_limit: UInt64) -> String:
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
        var folded = ascii_lower(slug)
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
        var row = String('{"additional_speed_tiers":[],"apply_patch_tool_type":"freeform","auto_compact_token_limit":') + String(compact_limit) + ',"availability_nux":null,"base_instructions":' + quote_json(instructions)
        row += ',"context_window":' + String(context_window) + ',"default_reasoning_level":"high","default_reasoning_summary":"none","default_service_tier":null,"default_verbosity":null,"description":' + quote_json(description)
        row += ',"display_name":' + quote_json(name) + ',"effective_context_window_percent":95,"experimental_supported_tools":[],"input_modalities":["text"],"max_context_window":' + String(context_window) + ',"priority":' + String(len(models) + 1)
        row += ',"service_tiers":[],"shell_type":"shell_command","slug":' + quote_json(slug) + ',"support_verbosity":false,"supported_in_api":true,"supported_reasoning_levels":['
        row += '{"description":"DeepSeek low reasoning effort","effort":"low"},{"description":"DeepSeek medium reasoning effort","effort":"medium"},{"description":"DeepSeek high reasoning effort","effort":"high"},{"description":"DeepSeek max reasoning effort","effort":"xhigh"}]'
        row += ',"supports_image_detail_original":false,"supports_parallel_tool_calls":true,"supports_reasoning_summaries":false,"supports_reasoning_summary_parameter":false,"supports_search_tool":false,"truncation_policy":{"limit":10000,"mode":"tokens"},"upgrade":null,"visibility":"list","web_search_tool_type":"text"}'
        models.append(row)
    return '{"models":[' + String(",").join(models) + "]}"


def _child_environment(home: String) -> List[String]:
    var excluded: List[String] = ["CODEX_HOME", "CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT", "NO_PROXY", "no_proxy", "LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "LD_ORIGIN_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", "PRODEX_RUNTIME_LOCAL_UPSTREAM", "PRODEX_RUNTIME_LOCAL_KEY", "PRODEX_RUNTIME_LOCAL_KEYS_JSON", "PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE", "PRODEX_RUNTIME_LOCAL_STRICT_TOOLS", "PRODEX_RUNTIME_LOCAL_BETA_BASE_URL"]
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
                duplicate = duplicate or ascii_lower(previous) == ascii_lower(value)
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
    var api_keys = List[String]()
    var keys_json = getenv("PRODEX_RUNTIME_LOCAL_KEYS_JSON", "\0")
    if keys_json != "\0":
        var keys = JsonDocument(keys_json)
        if keys.nodes[keys.root].kind != JSON_ARRAY:
            raise Error("local provider API keys must be a JSON array")
        for node in keys.nodes[keys.root].children:
            if keys.nodes[node].kind != JSON_STRING:
                raise Error("local provider API keys must be strings")
            var key = keys.string(node)
            _ = deepseek_request_headers([], key)
            api_keys.append(key^)
    else:
        var key = getenv("PRODEX_RUNTIME_LOCAL_KEY")
        _ = deepseek_request_headers([], key)
        api_keys.append(key^)
    _ = local_rewrite_upstream(upstream)
    var configured_mode = getenv("PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE", "\x00")
    var configured_strict = getenv("PRODEX_RUNTIME_LOCAL_STRICT_TOOLS", "\x00")
    var configured_beta = getenv("PRODEX_RUNTIME_LOCAL_BETA_BASE_URL", "\x00")
    var route = deepseek_runtime_route(Optional[String](configured_mode) if configured_mode != "\x00" else None, Optional[String](configured_strict) if configured_strict != "\x00" else None, Optional[String](configured_beta) if configured_beta != "\x00" else None)
    var listener = LoopbackHTTPListener("127.0.0.1:0")
    var output = RawFileDescriptor(1)
    output.write_bytes((listener.address + "\n").as_bytes())
    serve_local_rewrite(listener, upstream, api_keys, route[0], route[1], route[2], parent_fd=0, allow_local_file_access=True, web_search_mode=route[3])


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


def _deepseek_codex_args(home: String, workspace: String, model: String, address: String, context_window: UInt64, compact_limit: UInt64, model_supplied: Bool) -> List[String]:
    var args = List[String]()
    _config(args, "model_catalog_json", quote_json(home + "/prodex-deepseek-model-catalog.json"))
    _config(args, "projects", "{" + quote_json(workspace) + "={trust_level=\"trusted\"}}")
    _config(args, "model_provider", "\"prodex-deepseek\"")
    if model_supplied:
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
    return args^


def _sensitive_cli_flag(argument: String) -> Bool:
    var start = 0
    while start < argument.byte_length() and argument.as_bytes()[start] == 45:
        start += 1
    var end = start
    while end < argument.byte_length() and argument.as_bytes()[end] != 61:
        end += 1
    if start == end:
        return False
    var normalized = String()
    for byte in argument[byte=start:end].as_bytes():
        var value = Int(byte)
        if 48 <= value <= 57 or 65 <= value <= 90 or 97 <= value <= 122:
            if 65 <= value <= 90:
                value += 32
            normalized += chr(value)
    return normalized in [
        "authorization", "apikey", "xapikey", "authkey", "cookie", "setcookie", "token",
        "accesstoken", "refreshtoken", "idtoken", "secret", "password", "credential",
        "credentials", "email", "githublogin", "profilearn", "profilenameupstream", "starturl",
        "accountid", "chatgptaccountid", "proxyauthorization",
    ] or normalized.endswith("token") or normalized.find("apikey") >= 0 or normalized.find("privatekey") >= 0 or normalized.find("secret") >= 0 or normalized.find("password") >= 0 or normalized.find("cookie") >= 0 or normalized.find("credential") >= 0


def _dry_run_arg(argument: String, home: String, workspace: String) -> String:
    var compact_key = String("model_auto_compact_token_limit=")
    var numeric_compact_limit = argument.startswith(compact_key)
    if numeric_compact_limit:
        var digits = String(argument[byte=compact_key.byte_length():])
        numeric_compact_limit = digits.byte_length() > 0
        for byte in digits.as_bytes():
            numeric_compact_limit = numeric_compact_limit and 48 <= Int(byte) <= 57
    var equals = argument.find("=")
    var redacted = argument
    if equals > 0 and _sensitive_cli_flag(argument):
        redacted = String(argument[byte=:equals]) + "=<redacted>"
    elif not numeric_compact_limit:
        redacted = redact_log_text(argument)
    var was_redacted = redacted != argument
    var value = redacted.replace(home, "<redacted-path>").replace(workspace, "<redacted-path>")
    if (value.find(" ") >= 0 or value.find("\"") >= 0 or value.find("\t") >= 0) and not (was_redacted and value.find("<redacted>") >= 0):
        return quote_json(value)
    return value


def _dry_run_env_value(value: String, home: String, workspace: String) -> String:
    var redacted = redact_log_text(value)
    var was_redacted = redacted != value
    var rendered = redacted if was_redacted else quote_json(value)
    return rendered.replace(home, "<redacted-path>").replace(workspace, "<redacted-path>")


def _environment_value(environment: List[String], name: String) -> String:
    for entry in environment:
        var separator = entry.find("=")
        if separator == name.byte_length() and String(entry[byte=:separator]) == name:
            return String(entry[byte=separator + 1:])
    return String()


def _managed_optimizer_roots() -> List[String]:
    var roots = List[String]()
    var configured = getenv("PRODEX_OPTIMIZERS_HOME", "\0")
    if configured != "\0": roots.append(configured)
    var xdg = getenv("XDG_DATA_HOME", "\0")
    if xdg != "\0": roots.append(xdg + "/prodex-optimizers")
    var home = getenv("HOME", "")
    if home: roots.append(home + "/.local/share/prodex-optimizers")
    return roots^


def _first_regular_path(command: String) -> String:
    for candidate in _path_candidates(command, getenv("PATH", "\0")):
        try:
            var resolved = realpath(candidate)
            var info = lstat(resolved)
            if info.st_mode & 0o170000 == 0o100000:
                return resolved^
        except:
            continue
    return String()


def _managed_tool_present(tool: String, command: String = "") -> Bool:
    for root in _managed_optimizer_roots():
        if lexists(root + "/" + tool):
            return True
        if command and _executable_path(root + "/" + command):
            return True
    return False


def _managed_codebase_candidates(root: String) -> List[String]:
    var base = root if root else "."
    var checkout = base + "/codebase-memory-mcp"
    var candidates = List[String]()
    candidates.append(base + "/codebase-memory-mcp")
    candidates.append(checkout + "/codebase-memory-mcp")
    candidates.append(checkout + "/build/c/codebase-memory-mcp")
    candidates.append(checkout + "/bin/codebase-memory-mcp")
    return candidates^


def _dry_run_rtk_binary() raises -> String:
    for root in _managed_optimizer_roots():
        var candidate = _executable_path(root + "/rtk")
        if candidate:
            try:
                var info = lstat(root)
                if info.st_mode & 0o170000 != 0o040000:
                    raise Error("invalid managed optimizer root")
                var resolved_root = realpath(root)
                var prefix = resolved_root if resolved_root.endswith("/") else resolved_root + "/"
                if not candidate.startswith(prefix):
                    raise Error("managed RTK command escapes its root")
            except:
                raise Error("Super dry-run cannot report installed optional tools yet")
            return candidate^
    for candidate in _path_candidates("rtk", getenv("PATH", "\0")):
        var resolved = _executable_path(candidate)
        if resolved:
            return resolved^
    return String()


def _dry_run_probe_environment() -> List[String]:
    var environment = List[String]()
    for name in [String("PATH"), String("HOME"), String("TMPDIR"), String("TMP"), String("TEMP"), String("XDG_CACHE_HOME"), String("NPM_CONFIG_CACHE"), String("npm_config_cache"), String("CBM_CACHE_DIR")]:
        var value = getenv(name, "\0")
        if value != "\0":
            environment.append(name + "=" + value)
    environment.append("npm_config_userconfig=/dev/null")
    return environment^


def _dry_run_probe_first_line(bytes: List[UInt8]) -> String:
    var text = String(from_utf8_lossy=Span(bytes))
    for line in text.split("\n"):
        var value = trim_text(line)
        if value:
            return value^
    return String()


def _dry_run_semver_identifiers(value: String, prerelease: Bool) -> Bool:
    if not value:
        return False
    var start = 0
    var numeric = True
    for index in range(value.byte_length()):
        var byte = Int(value.as_bytes()[index])
        if byte == 46:
            if start == index or (prerelease and numeric and index - start > 1 and value.as_bytes()[start] == 48):
                return False
            start = index + 1
            numeric = True
        elif 48 <= byte <= 57:
            pass
        elif 65 <= byte <= 90 or 97 <= byte <= 122 or byte == 45:
            numeric = False
        else:
            return False
    return start < value.byte_length() and not (prerelease and numeric and value.byte_length() - start > 1 and value.as_bytes()[start] == 48)


# shortcut: only canonical RTK SemVer lines are accepted, broaden after other real banners are qualified.
def _dry_run_rtk_version_status(line: String) -> String:
    var invalid = "skipped (rtk did not report a recognizable semantic version: " + redact_log_text(line) + ")"
    if not line.startswith("rtk "):
        return invalid^
    var version_text = String(line[byte=4:])
    if version_text.startswith("v"):
        var stripped_version = String(version_text[byte=1:])
        version_text = stripped_version
    var dash = version_text.find("-")
    var plus = version_text.find("+")
    var core_end = version_text.byte_length()
    var prerelease = False
    if plus >= 0:
        if not _dry_run_semver_identifiers(String(version_text[byte=plus + 1:]), False):
            return invalid^
        core_end = plus
    if dash >= 0 and (plus < 0 or dash < plus):
        var prerelease_end = plus if plus >= 0 else version_text.byte_length()
        if not _dry_run_semver_identifiers(String(version_text[byte=dash + 1:prerelease_end]), True):
            return invalid^
        core_end = dash
        prerelease = True
    var components = String(version_text[byte=:core_end]).split(".")
    if len(components) != 3:
        return invalid^
    var version = List[UInt64]()
    for component in components:
        var part = String(component)
        var number: UInt64
        try:
            number = unsigned_value(part)
        except:
            return invalid^
        if String(number) != part:
            return invalid^
        version.append(number)
    var too_old = version[0] == UInt64(0) and version[1] < UInt64(46)
    too_old = too_old or (version[0] == UInt64(0) and version[1] == UInt64(46) and version[2] == UInt64(0) and prerelease)
    if too_old:
        return "skipped (" + redact_log_text(line) + " is too old; Prodex requires 0.46.0 or newer. Update rtk to the latest stable release (release-qualified reference: 1.1.0))"
    return "resolved (activation deferred until launch)"


def _dry_run_rtk_status() raises -> String:
    var binary = _dry_run_rtk_binary()
    if not binary:
        return "skipped (rtk was not found in managed roots or PATH)"
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(binary, [String("--version")], _dry_run_probe_environment(), "rtk health check", 5000, 65536, argv0=binary)
    except error:
        if String(error).find("timed out") >= 0:
            return "skipped (rtk health check timed out after 5s)"
        return "skipped (rtk health check failed)"
    var line = _dry_run_probe_first_line(probe.stdout)
    if not line:
        line = _dry_run_probe_first_line(probe.stderr)
    if not line:
        line = "available"
    if not probe.status.exit_code or probe.status.exit_code.value() != 0:
        return "skipped (version check exited with exit status: " + String(_child_exit_code(probe.status)) + ": " + redact_log_text(line) + ")"
    return _dry_run_rtk_version_status(line)


def _dry_run_codebase_version_supported(line: String) -> Bool:
    var prefix = String("codebase-memory-mcp ")
    if not line.startswith(prefix): return False
    var version = String(line[byte=prefix.byte_length():])
    if version == "dev": return True
    var plus = version.find("+")
    var end = version.byte_length()
    if plus >= 0:
        if not _dry_run_semver_identifiers(String(version[byte=plus + 1:]), False): return False
        end = plus
    var dash = version.find("-")
    var prerelease = String()
    if dash >= 0 and dash < end:
        prerelease = String(version[byte=dash + 1:end])
        if not _dry_run_semver_identifiers(prerelease, True): return False
        end = dash
    var components = String(version[byte=:end]).split(".")
    if len(components) != 3: return False
    var numbers = List[UInt64]()
    for component in components:
        var part = String(component)
        var number: UInt64
        try:
            number = unsigned_value(part)
        except:
            return False
        if String(number) != part: return False
        numbers.append(number)
    if numbers[0] > UInt64(0) or numbers[1] > UInt64(9): return True
    if numbers[1] < UInt64(9) or numbers[2] < UInt64(1): return False
    if numbers[2] > UInt64(1) or not prerelease: return True
    var identifiers = prerelease.split(".")
    var first = String(identifiers[0])
    # Compare the first identifier to the minimum's "rc", including numeric precedence.
    var first_numeric = True
    for byte in first.as_bytes():
        first_numeric = first_numeric and 48 <= Int(byte) <= 57
    if first_numeric: return False
    if first != "rc":
        var bytes = first.as_bytes()
        if Int(bytes[0]) != 114: return Int(bytes[0]) > 114
        if len(bytes) == 1: return False
        if Int(bytes[1]) != 99: return Int(bytes[1]) > 99
        return len(bytes) > 2
    if len(identifiers) < 2: return False
    var second = String(identifiers[1])
    return second != "0"


def _dry_run_codebase_status() raises -> String:
    var binary = String()
    for root in _managed_optimizer_roots():
        for candidate in _managed_codebase_candidates(root):
            if not exists(candidate):
                continue
            try:
                var resolved = realpath(candidate)
                var info = lstat(resolved)
                if info.st_mode & 0o170000 != 0o100000:
                    continue
                var root_path = root if root else "."
                var root_info = lstat(root_path)
                if root_info.st_mode & 0o170000 != 0o040000:
                    return "skipped (managed Codebase Memory root is not a real directory)"
                var resolved_root = realpath(root_path)
                var prefix = resolved_root if resolved_root.endswith("/") else resolved_root + "/"
                # Do not execute a managed symlink target until containment is known.
                if not resolved.startswith(prefix):
                    return "skipped (managed codebase-memory-mcp command escapes its root)"
                binary = resolved^
            except:
                return "skipped (managed codebase-memory-mcp health check failed)"
            if binary:
                break
        if binary:
            break
    if not binary:
        for candidate in _path_candidates("codebase-memory-mcp", getenv("PATH", "\0")):
            binary = _executable_path(candidate)
            if binary: break
    if not binary:
        return "skipped (codebase-memory-mcp was not found in managed roots or PATH)"
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(binary, [String("--version")], _dry_run_probe_environment(), "codebase-memory-mcp health check", 5000, 65536, argv0=binary)
    except error:
        if String(error).find("timed out") >= 0:
            return "skipped (codebase-memory-mcp health check timed out after 5s)"
        return "skipped (codebase-memory-mcp health check failed)"
    var line = _dry_run_probe_first_line(probe.stdout)
    if not line: line = _dry_run_probe_first_line(probe.stderr)
    if not line: line = "available"
    if not probe.status.exit_code or probe.status.exit_code.value() != 0:
        return "skipped (version check exited with exit status: " + String(_child_exit_code(probe.status)) + ": " + redact_log_text(line) + ")"
    if _dry_run_codebase_version_supported(line):
        return "resolved (activation deferred until launch)"
    return "skipped (codebase-memory-mcp lacks shared daemon coordination; Prodex requires 0.9.1-rc.1 or newer. Update to the latest stable release (release-qualified reference: 0.12.1))"


def _playwright_version_token(token: String) -> String:
    var start = 0
    var end = token.byte_length()
    while start < end:
        var byte = Int(token.as_bytes()[start])
        if 48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122 or byte in [43, 45, 46]: break
        start += 1
    while end > start:
        var byte = Int(token.as_bytes()[end - 1])
        if 48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122 or byte in [43, 45, 46]: break
        end -= 1
    while start < end and token.as_bytes()[start] == 118: start += 1
    var version = String(token[byte=start:end])
    var plus = version.find("+")
    var core_end = version.byte_length()
    if plus >= 0:
        if not _dry_run_semver_identifiers(String(version[byte=plus + 1:]), False): return String()
        core_end = plus
    var dash = version.find("-")
    var prerelease = False
    if dash >= 0 and dash < core_end:
        if not _dry_run_semver_identifiers(String(version[byte=dash + 1:core_end]), True): return String()
        core_end = dash
        prerelease = True
    var parts = String(version[byte=:core_end]).split(".")
    if len(parts) != 3: return String()
    var numbers = List[UInt64]()
    for part in parts:
        var text = String(part)
        var number: UInt64
        try:
            number = unsigned_value(text)
        except:
            return String()
        if String(number) != text: return String()
        numbers.append(number)
    var old = numbers[0] == UInt64(0) and numbers[1] == UInt64(0) and (numbers[2] < UInt64(79) or (numbers[2] == UInt64(79) and prerelease))
    if old:
        return "skipped (playwright-mcp " + version + " is too old; Prodex requires 0.0.79 or newer. Update playwright-mcp to the latest stable release (release-qualified reference: 0.0.83))"
    return "resolved (activation deferred until launch)"


def _dry_run_playwright_status(binary: String) -> String:
    var unavailable = String("skipped (Playwright MCP is not installed or is currently unavailable; install/update @playwright/mcp 0.0.79 or newer (latest stable reference: 0.0.83))")
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(binary, [String("--no-install"), "@playwright/mcp", "--version"], _dry_run_probe_environment(), "playwright-mcp health check", 5000, 65536, argv0=binary)
    except:
        return unavailable^
    if not probe.status.exit_code or probe.status.exit_code.value() != 0: return unavailable^
    try:
        _ = String(from_utf8=Span(probe.stdout))
        _ = String(from_utf8=Span(probe.stderr))
    except:
        return unavailable^
    var line = _dry_run_probe_first_line(probe.stdout)
    if not line: line = _dry_run_probe_first_line(probe.stderr)
    var token = String()
    for character in line.codepoints():
        var code = Int(character)
        if is_whitespace(code):
            var status = _playwright_version_token(token)
            if status: return status^
            token = String()
        else:
            token += chr(code)
    var status = _playwright_version_token(token)
    return status^ if status else unavailable^


def _dry_run_ponytail_node_status(binary: String) -> String:
    var probe: CapturedProcessOutput
    try:
        probe = capture_with_env(binary, [String("--version")], _dry_run_probe_environment(), "Node.js health check", 5000, 65536, argv0=binary)
    except error:
        if String(error).find("timed out") >= 0:
            return "Node.js health check timed out after 5s"
        return "Node.js health check failed"
    if probe.status.exit_code and probe.status.exit_code.value() != 0:
        return "Node.js health check exited with exit status: " + String(probe.status.exit_code.value())
    if not probe.status.exit_code:
        return "Node.js health check failed"
    return "Ponytail 4.9.0+ was not found under a managed optional-tool root; latest stable reference is 5.3.2"


def _dry_run_optional_tool_statuses() raises -> Tuple[String, String, String, String]:
    var present = _managed_tool_present("caveman")
    var node = _first_regular_path("node")
    var npx = _first_regular_path("npx")
    present = present or _managed_tool_present("ponytail")
    if present:
        raise Error("Super dry-run cannot report installed optional tools yet")
    var rtk_status = _dry_run_rtk_status()
    var codebase_status = _dry_run_codebase_status()
    var playwright_status = String("skipped (Node.js 18+ was not found on PATH)")
    var ponytail_status = String("Node.js was not found on PATH")
    if node and npx:
        playwright_status = _dry_run_playwright_status(npx)
    elif node:
        playwright_status = "skipped (npx was not found on PATH)"
    if node:
        ponytail_status = _dry_run_ponytail_node_status(node)
    return rtk_status^, codebase_status^, playwright_status^, ponytail_status^


def _print_dry_run_optional_tools(rtk_status: String, codebase_status: String, playwright_status: String, ponytail_status: String):
    var caveman_missing = "Caveman 2.3.1+ was not found under a managed optional-tool root; latest stable reference is 4.0.1"
    print("Optional tools:")
    if rtk_status.startswith("resolved "):
        print("  rtk: " + rtk_status)
    if codebase_status.startswith("resolved "):
        print("  codebase-memory-mcp: " + codebase_status)
    if playwright_status.startswith("resolved "):
        print("  playwright-mcp: " + playwright_status)
    print("  caveman: skipped (" + caveman_missing + ")")
    if not rtk_status.startswith("resolved "):
        print("  rtk: " + rtk_status)
    if not codebase_status.startswith("resolved "):
        print("  codebase-memory-mcp: " + codebase_status)
    if not playwright_status.startswith("resolved "):
        print("  playwright-mcp: " + playwright_status)
    print("  ponytail: skipped (" + ponytail_status + ")")


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
    var normalized = ascii_lower(trim_text(value))
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


def _deepseek_provider_panel(key_count: Int) raises:
    if not _launch_progress_fallback():
        return
    var rotation = String("Using one provider API key; API-key rotation is skipped")
    var quota_suffix = String("; quota preflight stays disabled.")
    if key_count > 1:
        rotation = "API-key rotation is enabled across " + String(key_count) + " keys"
    else:
        quota_suffix = " and quota preflight stays disabled."
    _print_fallback_stderr_panel(
        "Runtime Provider",
        "Using provider 'deepseek' through the local compatibility proxy. Smart Context rewrites require a proven tokenizer. " + rotation + quota_suffix,
    )


def _checked_deepseek_api_key(value: String, name: String) raises -> String:
    if not value:
        raise Error(name + " cannot be empty")
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            raise Error(name + " must not contain whitespace")
    return String(value)


def _deepseek_api_keys(value: String, supplied: Bool) raises -> List[String]:
    if supplied:
        var keys = List[String]()
        var key = _checked_deepseek_api_key(value, "--api-key")
        _ = deepseek_request_headers([], key)
        keys.append(key^)
        return keys^
    var multiple = getenv("DEEPSEEK_API_KEYS", "\0")
    if multiple != "\0":
        var keys = List[String]()
        var start = 0
        for index in range(multiple.byte_length()):
            var byte = Int(multiple.as_bytes()[index])
            if byte == 44 or byte == 59 or byte == 10:
                var key = trim_text(String(multiple[byte=start:index]))
                if key:
                    keys.append(key^)
                start = index + 1
        var key = trim_text(String(multiple[byte=start:]))
        if key:
            keys.append(key^)
        if not keys:
            raise Error("DEEPSEEK_API_KEYS cannot be empty")
        for key in keys:
            _ = deepseek_request_headers([], key)
        return keys^
    var single = getenv("DEEPSEEK_API_KEY", "\0")
    if single != "\0":
        var keys = List[String]()
        var key = _checked_deepseek_api_key(single, "DEEPSEEK_API_KEY")
        _ = deepseek_request_headers([], key)
        keys.append(key^)
        return keys^
    raise Error("DeepSeek provider requires --api-key or DEEPSEEK_API_KEY(S) in the environment")


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


def _exec(binary: String, child_path: String, argv0: String, home: String, model: String, upstream: String, api_keys: List[String], prompt: List[String], context_window: UInt64, compact_limit: UInt64, web_search_mode: String, strict_tools: Optional[String], beta_base_url: Optional[String], model_supplied: Bool) raises -> Int:
    _ = local_rewrite_worker_count()
    var environment = _child_environment(home)
    var probe_environment = _codex_probe_environment(environment)
    var version = _capture_codex_probe(binary, [String("--version")], probe_environment, "Codex version probe")
    if not version.status.exit_code or version.status.exit_code.value() != 0:
        raise Error(
            "Codex version probe failed for " + binary + " with status "
            + String(_child_exit_code(version.status)) + ". " + CODEX_INSTALL_GUIDANCE
        )
    var version_output = String(from_utf8_lossy=Span(version.stdout)) + "\n" + String(from_utf8_lossy=Span(version.stderr))
    if ascii_lower(version_output).find("codex") < 0:
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
    var keys_json = String("[")
    for index in range(len(api_keys)):
        if index: keys_json += ","
        keys_json += quote_json(api_keys[index])
    keys_json += "]"
    relay_environment.append("PRODEX_RUNTIME_LOCAL_KEYS_JSON=" + keys_json)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_WEB_SEARCH_MODE=" + web_search_mode)
    if strict_tools:
        relay_environment.append("PRODEX_RUNTIME_LOCAL_STRICT_TOOLS=" + strict_tools.value())
    if beta_base_url:
        relay_environment.append("PRODEX_RUNTIME_LOCAL_BETA_BASE_URL=" + beta_base_url.value())
    var relay: Process
    with open("/dev/null", "w") as errors:
        relay = spawn_with_env_stdio(realpath("/proc/self/exe"), [String("__modex-local-rewrite")], relay_environment, input.fd_in.value().value, output.fd_out.value().value, RawFileDescriptor(errors).value)
    input.set_output_only()
    output.set_input_only()
    try:
        var address = _ready(output, relay)
        var args = _deepseek_codex_args(home, String(cwd()), model, address, context_window, compact_limit, model_supplied)
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


def run_clean_deepseek_super(model: String, upstream: String, key: String, prompt: List[String], context_window: UInt64 = 0, compact_limit: UInt64 = 0, profile: String = "", profile_supplied: Bool = False, model_supplied: Bool = True, key_supplied: Bool = True, dry_run: Bool = False) raises -> Int:
    if not dry_run:
        _deepseek_launch_progress()
    _ = local_rewrite_upstream(upstream)
    var launch_context = context_window if context_window > 1 else UInt64(1048576)
    var launch_compact = min(compact_limit if compact_limit > 0 else UInt64(900000), launch_context - 1)
    var launch_model = trim_text(model)
    if not launch_model:
        launch_model = "deepseek-v4-pro"
    var root = app_root()
    var shared = shared_root(root)
    var shared_config = _clean_home(root, shared, profile_supplied, dry_run)
    if profile_supplied:
        raise Error("profile '" + profile + "' does not exist")
    var route = deepseek_runtime_route(shared_config[1], shared_config[2], shared_config[3])
    var catalog_config = TOMLDocument(shared_config[0])
    var catalog_model = String()
    if model_supplied:
        var model_literal = quote_json(launch_model)
        # The frozen catalog's CLI config scanner strips quotes without unescaping them.
        catalog_model = trim_text(String(model_literal[byte=1:model_literal.byte_length() - 1]))
    else:
        catalog_model = trim_text(catalog_config.string(catalog_config.get(catalog_config.root, "model")))
        if not catalog_model:
            catalog_model = "deepseek-v4-pro"
    if catalog_model.byte_length() > 4096:
        raise Error("DeepSeek model identifier exceeds 4096 bytes")
    var catalog_context = _catalog_config_number(catalog_config, "model_context_window", UInt64(1048576))
    var catalog_compact = min(_catalog_config_number(catalog_config, "model_auto_compact_token_limit", UInt64(900000)), catalog_context - 1)
    if dry_run:
        var optional_tool_statuses = _dry_run_optional_tool_statuses()
        var codex = _dry_run_codex_binary()
        var home = root + "/profiles/.prodex-overlay-" + new_uuid7()
        var args = List[String](capacity=32)
        args.append("--dangerously-bypass-approvals-and-sandbox")
        args.append("exec")
        args.extend(_deepseek_codex_args(home, String(cwd()), launch_model, "127.0.0.1:0", launch_context, launch_compact, model_supplied))
        args.extend(prompt.copy())
        var report_model = String("(codex default)")
        if model_supplied:
            report_model = launch_model
        else:
            var model_node = catalog_config.get(catalog_config.root, "model")
            if model_node >= 0 and catalog_config.nodes[model_node].kind == TOML_STRING:
                var configured_model = trim_text(catalog_config.string(model_node))
                if configured_model:
                    report_model = configured_model
        print("Prodex dry run: launch diagnostics")
        print("Flow: optional-tools")
        var binary_parts = codex.split("/")
        var binary_name = String(codex)
        if binary_parts[len(binary_parts) - 1]:
            binary_name = String(binary_parts[len(binary_parts) - 1])
        print("Binary: " + binary_name)
        print("Provider: prodex-deepseek")
        print("Model: " + redact_log_text(report_model))
        print("CODEX_HOME: <CODEX_HOME>")
        print("Runtime proxy: would be enabled with mount /v1")
        print("Args:")
        var redact_next = False
        for argument in args:
            if redact_next:
                print("  <redacted>")
                redact_next = argument.startswith("-") and _sensitive_cli_flag(argument) and argument.find("=") < 0
            else:
                print("  " + _dry_run_arg(argument, home, String(cwd())))
                redact_next = argument.startswith("-") and _sensitive_cli_flag(argument) and argument.find("=") < 0
        var environment = _child_environment(home)
        print("Env:")
        print("  CODEX_HOME=<CODEX_HOME>")
        print("  NO_PROXY=" + _dry_run_env_value(_environment_value(environment, "NO_PROXY"), home, String(cwd())))
        print("  no_proxy=" + _dry_run_env_value(_environment_value(environment, "no_proxy"), home, String(cwd())))
        print("  CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT=" + _environment_value(environment, "CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT"))
        print("Removed env:")
        for name in [String("CODEX_SANDBOX"), String("CODEX_SANDBOX_NETWORK_DISABLED"), String("DYLD_FRAMEWORK_PATH"), String("DYLD_INSERT_LIBRARIES"), String("DYLD_LIBRARY_PATH"), String("LD_AUDIT"), String("LD_LIBRARY_PATH"), String("LD_ORIGIN_PATH"), String("LD_PRELOAD")]:
            print("  " + name)
        print("Codex/TUI not started because --dry-run was set.")
        print("Profile: (active/default)")
        _print_dry_run_optional_tools(optional_tool_statuses[0], optional_tool_statuses[1], optional_tool_statuses[2], optional_tool_statuses[3])
        print("Dry run: optional overlays and services are not started.")
        print("Sub-agent: disabled")
        print("Sub-agent inherited Presidio: disabled")
        print("Sub-agent local URL: absent")
        print("Sub-agent recursion disabled: yes")
        print("Sub-agent overlay: absent")
        print()
        print("Presidio redaction: disabled (not started)")
        return 0
    _ = ensure_app_root()
    _private_directory(shared)
    _private_directory(root + "/profiles")
    var selected_keys = _deepseek_api_keys(key, key_supplied)
    _deepseek_provider_panel(len(selected_keys))
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
            catalog.write(deepseek_model_catalog(catalog_model, catalog_context, catalog_compact))
        var codex = _codex_binary()
        var result = _exec(codex[0], codex[1], codex[2], home, launch_model, upstream, selected_keys, prompt, launch_context, launch_compact, route[3], shared_config[2], shared_config[3], model_supplied)
        _remove_overlay(home)
        return result
    except:
        _remove_overlay(home)
        raise
