# Compile/platform probe for the standard library's internal POSIX socket layer.
# This does not provide a production transport API.

from std.net._sys.inet import in_addr
from std.net._sys.unix import AF_INET, SOCK_DGRAM, sockaddr_in, socket
from std.sys import size_of
from std.sys._libc import close


def main():
    var fd = socket(AF_INET, SOCK_DGRAM, 0)
    if fd >= 0:
        assert close(fd) == 0

    var address = sockaddr_in(port=UInt16(53), addr=in_addr(s_addr=0))
    print(size_of[sockaddr_in](), address.port())
