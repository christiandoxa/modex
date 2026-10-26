"""Native clean-home DeepSeek exec launch and direct-child ownership."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.net._sys.unix import F_GETFL, F_SETFL, O_NONBLOCK
from std.os import getenv, getuid, listdir, lstat, mkdir, remove, rmdir, symlink
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
from .process_spawn import capture_with_env, inherited_environment, spawn_with_env, spawn_with_env_stdio, wait_or_kill
from .provider_deepseek_transport import deepseek_request_headers
from .runtime_local_rewrite import local_rewrite_upstream, serve_local_rewrite
from .text import trim_text
from .uuid7 import new_uuid7


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


def _clean_home(root: String, shared: String) raises:
    # shortcut: existing profile/config reconciliation needs locked storage; admit only an empty base home and no saved account state.
    if lexists(shared):
        var info = lstat(shared)
        if info.st_mode & 0o170000 != 0o040000 or info.st_uid != getuid() or info.st_mode & 0o077 or listdir(shared):
            raise Error("Super clean-home launch cannot reconcile existing Codex data yet")
    if lexists(root):
        for name in listdir(root):
            if name != "update-check.json" and name != "profiles":
                raise Error("Super clean-home launch cannot reconcile existing application state yet")
            if name == "profiles" and (lstat(root + "/profiles").st_mode & 0o170000 != 0o040000 or listdir(root + "/profiles")):
                raise Error("Super clean-home launch requires an empty profiles directory")


def _ascii_lower(value: String) -> String:
    var result = String()
    for character in value.codepoints():
        var code = Int(character)
        result += chr(code + 32 if 65 <= code <= 90 else code)
    return result


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
    var excluded: List[String] = ["CODEX_HOME", "CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT", "NO_PROXY", "no_proxy", "LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "LD_ORIGIN_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "PRODEX_RUNTIME_LOCAL_UPSTREAM", "PRODEX_RUNTIME_LOCAL_KEY"]
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


def run_local_rewrite_child() raises:
    """Private self-process entrypoint; credentials stay out of argv and output."""
    var upstream = getenv("PRODEX_RUNTIME_LOCAL_UPSTREAM")
    var key = getenv("PRODEX_RUNTIME_LOCAL_KEY")
    _ = local_rewrite_upstream(upstream)
    _ = deepseek_request_headers([], key)
    var listener = LoopbackHTTPListener("127.0.0.1:0")
    var output = RawFileDescriptor(1)
    output.write_bytes((listener.address + "\n").as_bytes())
    serve_local_rewrite(listener, upstream, key, parent_fd=0, allow_local_file_access=True)


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


def _exec(binary: String, home: String, model: String, upstream: String, key: String, prompt: List[String], context_window: UInt64, compact_limit: UInt64) raises -> Int:
    var environment = _child_environment(home)
    var version = capture_with_env(binary, [String("--version")], environment, "Codex version probe")
    if not version.status.exit_code or version.status.exit_code.value() != 0 or not String(from_utf8=Span(version.stdout)).startswith("codex-cli "):
        raise Error("Codex version probe failed")
    var input = Pipe()
    var output = Pipe()
    var relay_environment = _child_environment(home)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_UPSTREAM=" + upstream)
    relay_environment.append("PRODEX_RUNTIME_LOCAL_KEY=" + key)
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
        _config(args, "model", quote_json(model))
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
        var legacy = run_super_hook_trust_preflight(binary, String(cwd()), args, environment)
        var launch = List[String]()
        if legacy:
            launch.append("--dangerously-bypass-hook-trust")
        launch.append("--dangerously-bypass-approvals-and-sandbox")
        launch.append("exec")
        launch.extend(args^)
        launch.extend(prompt.copy())
        var child = spawn_with_env(binary, launch, environment)
        var result: ProcessStatus
        try:
            while not child.poll().has_exited():
                if relay.poll().has_exited():
                    raise Error("local provider exited while Codex was running")
                sleep(0.005)
            result = child.wait()
        except:
            _ = child.kill()
            _ = wait_or_kill(child, 1)
            raise
        _ = wait_or_kill(relay, 1)
        input.set_input_only()
        return result.exit_code.value() if result.exit_code else 1
    except:
        _ = wait_or_kill(relay, 1)
        input.set_input_only()
        raise


def run_clean_deepseek_super(model: String, upstream: String, key: String, prompt: List[String], context_window: UInt64 = 0, compact_limit: UInt64 = 0) raises -> Int:
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
    var binary = getenv("PRODEX_CODEX_BIN")
    if not binary.startswith("/") or "\x00" in binary:
        raise Error("Super clean-home launch requires an absolute PRODEX_CODEX_BIN")
    var root = app_root()
    var shared = shared_root(root)
    _clean_home(root, shared)
    _ = ensure_app_root()
    _private_directory(shared)
    _private_directory(root + "/profiles")
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
            config.write("")
        with open(home + "/auth.json", "w") as auth:
            auth.write("{\"OPENAI_API_KEY\":\"prodex-runtime-provider\",\"agent_identity\":null,\"auth_mode\":\"apikey\",\"last_refresh\":null,\"tokens\":null}")
        with open(home + "/prodex-deepseek-model-catalog.json", "w") as catalog:
            # Frozen exact-value lookup ignores numeric -c overrides when building the catalog.
            catalog.write(deepseek_model_catalog(catalog_model))
        var result = _exec(binary, home, launch_model, upstream, key, prompt, launch_context, launch_compact)
        _remove_overlay(home)
        return result
    except:
        _remove_overlay(home)
        raise
