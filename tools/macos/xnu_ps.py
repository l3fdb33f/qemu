#!/usr/bin/env python3
# Full XNU (pid, name) process list from the live Monterey kernel under panda-ng.
import socket, time, re, os
SOCK = os.path.expanduser("~/macos/mac_mon.sock")
ALLPROC = 0xffffff8006b17770   # KC __DATA + dSYM __DATA off (this boot)
OFF_NEXT, OFF_PID, OFF_PPID, OFF_TASK, OFF_COMM = 0, 104, 40, 16, 1029
KBASE = 0xffffff8000000000
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(SOCK); s.settimeout(3.0)
def cmd(c):
    s.sendall((c+"\n").encode()); time.sleep(0.05); out=b""
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
def rdname(proc):
    # name window covers p_comm(~+1029) and p_name(~+1046); take longest run
    r = cmd("x/64bx 0x%x" % (proc + 1020))
    bs = bytes(int(x,16) for x in re.findall(r"\b0x([0-9a-fA-F]{2})\b", r))
    runs = re.findall(rb"[ -~]{2,}", bs)
    return max(runs, key=len).decode(errors="replace") if runs else ""
def isk(v): return v is not None and v>=KBASE
cmd("stop")
for i in range(400):
    if cpl()==0: break
    cmd("cont"); time.sleep(0.02); cmd("stop")
rows=[]; p=rdq(ALLPROC); seen=set()
while isk(p) and p not in seen and len(rows)<600:
    seen.add(p)
    rows.append((rdw(p+OFF_PID), rdw(p+OFF_PPID), rdname(p), p))
    p = rdq(p+OFF_NEXT)
cmd("cont"); s.close()
rows.sort(key=lambda r: (r[0] if r[0] is not None else 1<<31))
print("==== XNU process list (live Monterey under panda-ng): %d procs ====" % len(rows))
print("  PID   PPID  COMMAND            PROC")
for pid, ppid, comm, pr in rows:
    print("  %-5s %-5s %-18s %#x" % (pid, ppid, comm, pr))
