"""Expose native argv projection to the separate differential harness."""

from std.collections import List
from std.sys import argv

from modex.app_server_args import project_app_server_config_args
from modex.json import quote_json


def main() raises:
    var arguments = argv()
    if len(arguments) < 2:
        raise Error("expected inline configuration mode")
    var runtime_args = List[String]()
    for index in range(2, len(arguments)):
        runtime_args.append(String(arguments[index]))
    var projected = project_app_server_config_args(runtime_args, arguments[1] == "1")
    var output = String("[")
    for index in range(len(projected)):
        if index:
            output += ","
        output += quote_json(projected[index])
    print(output + "]")
