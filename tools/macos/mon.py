#!/usr/bin/env python3
# Send a QEMU monitor command over a unix socket and print the reply.
#   mon.py <sock> "<command>"   e.g.  mon.py ~/macos/mac_mon.sock "sendkey ret"
import socket, sys, time, os
sock = os.path.expanduser(sys.argv[1]); cmd = sys.argv[2]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(sock)
time.sleep(0.2); s.recv(65536)            # banner
s.sendall((cmd + "\n").encode()); time.sleep(0.4)
out = b""
s.settimeout(1.0)
try:
    while True:
        d = s.recv(65536)
        if not d: break
        out += d
except socket.timeout:
    pass
print(out.decode(errors="replace"))
