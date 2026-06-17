#!/usr/bin/env python3
# Decode an Apple pbzx Payload (chunked XZ) to a raw cpio stream on stdout.
import sys, struct, lzma
f = open(sys.argv[1], "rb")
assert f.read(4) == b"pbzx", "not a pbzx file"
f.read(8)  # flags
out = sys.stdout.buffer
while True:
    hdr = f.read(16)
    if len(hdr) < 16:
        break
    uncomp, comp = struct.unpack(">QQ", hdr)
    data = f.read(comp)
    if comp == uncomp:
        out.write(data)            # stored chunk
    else:
        out.write(lzma.decompress(data))  # XZ chunk
