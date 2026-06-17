#!/usr/bin/env python3
# Parse LC_SEGMENT_64 vmaddrs from the KDK kernel dSYM Mach-O.
import struct, sys
f = open(sys.argv[1], "rb")
data = f.read()
magic, = struct.unpack_from("<I", data, 0)
assert magic == 0xfeedfacf, hex(magic)
ncmds, = struct.unpack_from("<I", data, 16)
off = 32
segs = {}
for _ in range(ncmds):
    cmd, cmdsize = struct.unpack_from("<II", data, off)
    if cmd == 0x19:  # LC_SEGMENT_64
        name = data[off+8:off+24].split(b"\x00")[0].decode()
        vmaddr, vmsize = struct.unpack_from("<QQ", data, off+24)
        segs[name] = (vmaddr, vmsize)
    off += cmdsize
for n, (a, sz) in segs.items():
    print("%-16s vmaddr=0x%x size=0x%x end=0x%x" % (n, a, sz, a+sz))

ALLPROC = 0xffffff8000e93770
KERNPROC = 0xffffff8000f03a38
for nm, addr in [("allproc", ALLPROC), ("kernproc", KERNPROC)]:
    for n, (a, sz) in segs.items():
        if a <= addr < a+sz:
            print("%s 0x%x is in dSYM segment %s (base 0x%x, off 0x%x)" % (nm, addr, n, a, addr-a))
            break
