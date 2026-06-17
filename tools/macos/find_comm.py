#!/usr/bin/env python3
import socket, time, re, os
SOCK = os.path.expanduser("~/macos/mac_mon.sock")
ALLPROC = 0xffffff8006b17770
OFF_NEXT, OFF_PID = 0, 104
KBASE = 0xffffff8000000000
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(SOCK); s.settimeout(3.0)
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
def rdq(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1gx 0x%x"%a)); return int(m.group(1),16) if m else None
def rdw(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1wx 0x%x"%a)); return int(m.group(1),16) if m else None
def rdbytes(a, n):
    out = b""
    got = []
    step = 256
    for o in range(0, n, step):
        r = cmd("x/%dbx 0x%x" % (min(step, n-o), a+o))
        # drop the address tokens (16-hex) then collect 2-hex bytes
        got += [int(x, 16) for x in re.findall(r"\b0x([0-9a-fA-F]{2})\b", r)]
    return bytes(got[:n])
def isk(v): return v is not None and v>=KBASE
cmd("stop")
for i in range(400):
    if cpl()==0: break
    cmd("cont"); time.sleep(0.02); cmd("stop")
# walk to find pid1 and pid0 procs
p = rdq(ALLPROC); seen=set(); targets={}
while isk(p) and p not in seen and len(seen)<500:
    seen.add(p); pid = rdw(p+OFF_PID)
    if pid in (0,1,2): targets[pid]=p
    p = rdq(p+OFF_NEXT)
print("found target procs:", {k:hex(v) for k,v in targets.items()})
for pid, pr in sorted(targets.items()):
    b = rdbytes(pr, 1488)
    print("\n=== pid %d proc @ 0x%x : ASCII runs (>=3) ===" % (pid, pr))
    for m in re.finditer(rb"[ -~]{3,}", b):
        print("  off %4d: %r" % (m.start(), m.group().decode()))
cmd("cont"); s.close()
