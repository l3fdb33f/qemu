#!/usr/bin/env python3
import socket, time, re, os
SOCK = os.path.expanduser("~/macos/mac_mon.sock")
ALLPROC_S = 0xffffff8000e93770
MH_S      = 0xffffff8000200000   # _mh_execute_header static
OFF_NEXT, OFF_PID = 0, 104
KBASE = 0xffffff8000000000
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
def rdq(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1gx 0x%x"%a)); return int(m.group(1),16) if m else None
def rdw(a):
    m=re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1wx 0x%x"%a)); return int(m.group(1),16) if m else None
def isk(v): return v is not None and v>=KBASE

cmd("stop")
got=False
for i in range(400):
    if cpl()==0: got=True; break
    cmd("cont"); time.sleep(0.02); cmd("stop")
print("CPL0 halt:", got)

# A) scan for kernel Mach-O header (feedfacf) -> derive slide
print("\n--- kernel header (feedfacf) scan @ MH_S+slide, step2MB, 0..1GB ---")
hdr_slide=None
for cand in range(0, 0x40000000, 0x200000):
    v=rdw(MH_S+cand)
    if v==0xfeedfacf:
        print("  feedfacf at slide=0x%x (addr 0x%x)" % (cand, MH_S+cand)); hdr_slide=cand; break
print("  header slide:", hex(hdr_slide) if hdr_slide is not None else "not found in 1GB")

# B) dump all mapped allproc candidates with a short walk
print("\n--- allproc candidates (kptr at ALLPROC_S+slide), 0..1GB step2MB ---")
n=0
for cand in range(0, 0x40000000, 0x200000):
    first=rdq(ALLPROC_S+cand)
    if not isk(first): continue
    n+=1
    pids=[]; p=first; seen=set()
    for _ in range(12):
        if not isk(p) or p in seen: break
        seen.add(p); pids.append(rdw(p+OFF_PID)); p=rdq(p+OFF_NEXT)
    print("  slide=0x%-9x lh_first=0x%x pids=%s" % (cand, first, pids))
print("mapped candidates:", n)

# C) if header slide found, test allproc at THAT slide
if hdr_slide is not None:
    f=rdq(ALLPROC_S+hdr_slide); pids=[]; p=f; seen=set()
    for _ in range(15):
        if not isk(p) or p in seen: break
        seen.add(p); pids.append(rdw(p+OFF_PID)); p=rdq(p+OFF_NEXT)
    print("\nallproc@headerslide: lh_first=%s pids=%s" % (hex(f) if f else "?", pids))
cmd("cont"); s.close()
