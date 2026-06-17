#!/usr/bin/env python3
import socket, time, re, os
SOCK = os.path.expanduser("~/macos/mac_mon.sock")
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(SOCK); s.settimeout(2.0)
def cmd(c):
    s.sendall((c+"\n").encode()); time.sleep(0.06); out=b""
    try:
        while True:
            d=s.recv(65536)
            if not d: break
            out+=d
            if out.rstrip().endswith(b"(qemu)"): break
    except socket.timeout: pass
    return out.decode(errors="replace")
time.sleep(0.3); s.recv(65536)
def cpl():
    m=re.search(r"\bCS =([0-9a-fA-F]{4})", cmd("info registers")); return (int(m.group(1),16)&3) if m else None
def rdw(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1wx 0x%x"%a)); return int(m.group(1),16) if m else None
def rdq(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1gx 0x%x"%a)); return int(m.group(1),16) if m else None
def rdbytes(a, n):
    # read n bytes via x/<n>bx, return list
    out = cmd("x/%dbx 0x%x" % (n, a))
    return [int(x,16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", out)]
cmd("stop")
for i in range(400):
    if cpl()==0: break
    cmd("cont"); time.sleep(0.02); cmd("stop")
SLIDE=0x5800000
H=0xffffff8000200000+SLIDE
print("header @ 0x%x: magic=0x%x cputype=0x%x cpusub=0x%x filetype=0x%x ncmds=%d" % (
    H, rdw(H), rdw(H+4), rdw(H+8), rdw(H+12), rdw(H+16)))
# walk load commands looking for LC_SEGMENT_64 (0x19); print segname + vmaddr
ncmds = rdw(H+16)
off = H + 32
print("segments (name @ link-vmaddr, size):")
for _ in range(min(ncmds, 60)):
    cmd_t = rdw(off); cmdsize = rdw(off+4)
    if cmdsize == 0: break
    if cmd_t == 0x19:  # LC_SEGMENT_64
        nm = bytes(rdbytes(off+8, 16)).split(b"\x00")[0].decode(errors="replace")
        vmaddr = rdq(off+24); vmsize = rdq(off+32)
        print("  %-16s 0x%x (size 0x%x) -> runtime 0x%x" % (nm, vmaddr, vmsize, vmaddr+SLIDE))
    off += cmdsize
# test a text symbol: _start static 0xffffff8000100000
print("\n_start@static+slide (0x%x) first bytes: %s" % (0xffffff8000100000+SLIDE,
      bytes(rdbytes(0xffffff8000100000+SLIDE, 8)).hex()))
cmd("cont"); s.close()
