#!/usr/bin/env python3
import socket, time, re, os
SOCK = os.path.expanduser("~/macos/mac_mon.sock")
ALLPROC  = 0xffffff8006b17770   # KC __DATA base + dSYM __DATA offset 0x293770
KERNPROC = 0xffffff8006490a38   # KC __DATA_CONST base + offset 0x6ca38
OFF_NEXT, OFF_PID, OFF_TASK = 0, 104, 16
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
def rdstr(a, n=20):
    out = cmd("x/%dbx 0x%x" % (n, a))
    bs = [int(x,16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", out)]
    s2 = bytes(bs).split(b"\x00")[0]
    return s2.decode(errors="replace")
def isk(v): return v is not None and v>=KBASE
cmd("stop")
for i in range(400):
    if cpl()==0: break
    cmd("cont"); time.sleep(0.02); cmd("stop")
first = rdq(ALLPROC)
print("allproc.lh_first = %s" % (hex(first) if first else "?"))
procs=[]; p=first; seen=set()
while isk(p) and p not in seen and len(procs)<500:
    seen.add(p)
    procs.append((p, rdw(p+OFF_PID), rdq(p+OFF_TASK)))
    p = rdq(p+OFF_NEXT)
print("==== allproc walk: %d procs ====" % len(procs))
# scan a candidate comm offset by dumping bytes at a few offsets of the first proc
for pr, pid, task in procs[:35]:
    nm = rdstr(pr + 0x381, 17)  # heuristic p_comm guess; refine below
    print("  pid=%-6s task=%#x  proc=%#x" % (pid, task or 0, pr))
kp = rdq(KERNPROC)
print("kernproc -> %s pid=%s" % (hex(kp) if kp else "?", rdw(kp+OFF_PID) if isk(kp) else "?"))
pids=[x[1] for x in procs if x[1] is not None]
print("SUMMARY: %d procs, pids %s..%s, pid0=%s pid1=%s" % (len(procs), min(pids) if pids else "?", max(pids) if pids else "?", 0 in pids, 1 in pids))
cmd("cont"); s.close()
