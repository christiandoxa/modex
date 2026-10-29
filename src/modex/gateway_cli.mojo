"""Gateway arguments and the captured DeepSeek startup failures."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.os import getuid, listdir, lstat, stat
from std.os.path import exists

from .cli import argument_name, session_cli_error
from .paths import ensure_app_root, shared_root
from .sessions import checked_session_file
from .text import trim_text
from .toml import TOMLDocument


@fieldwise_init
struct GatewayOptions(Copyable):
    var listen: String
    var provider: String
    var base_url: String
    var api_key: Optional[String]
    var smart_context: Bool
    var presidio: Bool
    var no_presidio: Bool
    var help: Bool


def gateway_help(executable: String) -> String:
    return "Run a lean OpenAI-compatible provider gateway.\n\nUsage: " + executable + " gateway [OPTIONS]\n\nOptions:\n      --listen <ADDR>        Address to bind the OpenAI-compatible gateway to. Defaults to loopback with an ephemeral port\n      --provider <PROVIDER>  External provider preset. Omit for an OpenAI-compatible upstream\n      --base-url <URL>       Upstream base URL [alias: --url]\n      --api-key <KEY>        Provider API key. Prefer provider-specific environment variables\n      --smart-context        Enable Smart Context Autopilot\n      --presidio             Enable Presidio request-body redaction\n      --no-presidio          Disable policy-enabled Presidio redaction\n  -h, --help                 Print help\n"


def _label(name: String) -> String:
    if name == "--listen": return name + " <ADDR>"
    if name == "--provider": return name + " <PROVIDER>"
    if name == "--base-url": return name + " <URL>"
    if name == "--api-key": return name + " <KEY>"
    return name


def parse_gateway_arguments(args: List[String], executable: String) raises -> GatewayOptions:
    var options = GatewayOptions("127.0.0.1:0", "", "", Optional[String](), False, False, False, False)
    var seen = List[String]()
    var group_usage = False
    var conflict_first = String()
    var conflict_second = String()
    var index = 2
    while index < len(args):
        var argument = args[index]
        if argument == "--":
            if index + 1 < len(args):
                raise session_cli_error(
                    "unexpected argument '" + args[index + 1] + "' found",
                    executable + " gateway [OPTIONS]",
                )
            break
        if argument == "--help" or (argument.startswith("-h") and not argument.startswith("--")):
            options.help = True
            return options^
        if argument.startswith("--help="):
            var value = String(argument.split("=", maxsplit=1)[1])
            var usage = executable + " gateway --help"
            if group_usage:
                usage += " <--listen <ADDR>|--provider <PROVIDER>|--base-url <URL>|--api-key <KEY>|--smart-context|--presidio|--no-presidio>"
            raise session_cli_error(
                "unexpected value '" + value + "' for '--help' found; no more were expected",
                usage,
            )
        var name = argument_name(argument)
        if name == "--url": name = "--base-url"
        var value_option = name == "--listen" or name == "--provider" or name == "--base-url" or name == "--api-key"
        var switch_option = name == "--smart-context" or name == "--presidio" or name == "--no-presidio"
        if not value_option and not switch_option:
            var usage = executable + " gateway"
            if seen:
                for prior in seen:
                    usage += " " + _label(prior)
            else:
                usage += " [OPTIONS]"
            raise session_cli_error("unexpected argument '" + name + "' found", usage)
        if name in seen:
            raise session_cli_error("the argument '" + _label(name) + "' cannot be used multiple times", executable + " gateway [OPTIONS]")
        seen.append(name)
        if value_option:
            var value: String
            if "=" in argument:
                group_usage = True
                value = String(argument.split("=", maxsplit=1)[1])
            else:
                if index + 1 >= len(args) or (args[index + 1].startswith("-") and args[index + 1] != "-"):
                    raise session_cli_error("a value is required for '" + _label(name) + "' but none was supplied")
                index += 1
                value = args[index]
            if name == "--listen": options.listen = value
            elif name == "--base-url": options.base_url = value
            elif name == "--api-key": options.api_key = value
            else:
                var provider = trim_text(value).lower()
                if provider == "claude": provider = "anthropic"
                if provider == "github-copilot" or provider == "github_copilot": provider = "copilot"
                if provider != "deepseek" and provider != "anthropic" and provider != "copilot" and provider != "gemini" and provider != "kiro":
                    raise session_cli_error("invalid value '" + value + "' for '--provider <PROVIDER>': invalid --provider: supported values are anthropic, copilot, deepseek, gemini, kiro, got \"" + provider + "\"")
                options.provider = provider
        else:
            if "=" in argument:
                raise session_cli_error("unexpected value '" + String(argument.split("=", maxsplit=1)[1]) + "' for '" + name + "' found; no more were expected", executable + " gateway " + name)
            group_usage = True
            if name == "--smart-context": options.smart_context = True
            elif name == "--presidio":
                options.presidio = True
                if options.no_presidio and not conflict_second:
                    conflict_first = "--no-presidio"
                    conflict_second = name
            else:
                options.no_presidio = True
                if options.presidio and not conflict_second:
                    conflict_first = "--presidio"
                    conflict_second = name
        index += 1
    if conflict_second:
        var usage = executable + " gateway"
        var skipped_conflict = False
        for name in seen:
            if name == conflict_second and not skipped_conflict:
                skipped_conflict = True
                continue
            usage += " " + _label(name)
        raise session_cli_error(
            "the argument '" + conflict_first + "' cannot be used with '" + conflict_second + "'",
            usage,
        )
    return options^


def run_gateway(options: GatewayOptions) raises:
    if options.provider != "deepseek":
        raise Error("this Modex development build has not implemented the requested gateway provider")
    var root = ensure_app_root()
    for name in listdir(root):
        if name == "state.json" or name == "state.last-good.json":
            raise Error("gateway startup for existing application state is not implemented by this Modex build")
        if name == "policy.toml":
            raise Error("gateway runtime policy loading is not implemented by this Modex build")
    var shared = shared_root(root)
    if exists(shared):
        var directory = lstat(shared)
        if (directory.st_mode & 0o170000) != 0o040000 or directory.st_uid != getuid() or (directory.st_mode & 0o022) != 0:
            raise Error("gateway Codex home requires an owned directory without shared write access")
        for name in listdir(shared):
            if name != "config.toml": continue
            var file = checked_session_file(shared + "/config.toml")
            var opened = stat("/proc/self/fd/" + String(RawFileDescriptor(file).value))
            if opened.st_uid != getuid() or (opened.st_mode & 0o022) != 0:
                raise Error("gateway Codex config requires an owned file without shared write access")
            var bytes = file.read_bytes(1048577)
            if len(bytes) > 1048576:
                raise Error("gateway Codex config exceeds the supported size")
            var config = TOMLDocument(String(from_utf8=Span(bytes)))
            if config.string(config.get(config.root, "model_provider")) == "prodex-deepseek":
                # The frozen gateway forces its OpenAI proxy and excludes local rewrite.
                raise Error("gateway provider does not expose an OpenAI-compatible proxy")
            raise Error("gateway startup for this Codex configuration is not implemented by this Modex build")
    raise Error("no active profile selected and no Codex-compatible profiles are available; use `prodex use --profile <name>` or pass --profile")
