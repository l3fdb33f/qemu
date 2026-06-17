#!/usr/bin/env python3
# Walk XNU allproc via QEMU monitor. Handles KASLR (finds slide via the
# vm_kernel_slide global) and KPTI (reads in a CPL=0 halt).
import socket, sys, time, re, os

SOCK = os.path.expanduser("~/macos/mac_mon.sock")
# static (unslid) ISF addresses
ALLPROC_S  = 0xffffff8000e93770
KERNPROC_S = 0xffffff8000f03a38
VM_SLIDE_S = 0xffffff8000e32c90
OFF_NEXT = 0
OFF_PID  = 104
OFF_TASK = 16
KBASE    = 0xffffff8000000000

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(SOCK)
s.settimeout(2.0)
def cmd(c):
    s.sendall((c + "\n").encode()); time.sleep(0.08)
    out = b""
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            out += d
            if out.rstrip().endswith(b"(qemu)"): break
    except socket.timeout:
        pass
    return out.decode(errors="replace")
time.sleep(0.3); s.recv(65536)

def cpl():
    r = cmd("info registers")
    m = re.search(r"\bCS =([0-9a-fA-F]{4})", r)
    return (int(m.group(1), 16) & 3) if m else None

def rdq(addr):
    m = re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1gx 0x%x" % addr))
    return int(m.group(1), 16) if m else None

def rdw(addr):
    m = re.search(r":\s*0x([0-9a-fA-F]+)", cmd("x/1wx 0x%x" % addr))
    return int(m.group(1), 16) if m else None

def is_kptr(v): return v is not None and v >= KBASE

# 1) halt in kernel context (CPL0) so the kernel half is mapped despite KPTI
cmd("stop")
got = False
for i in range(400):
    c = cpl()
    if c == 0: got = True; break
    cmd("cont"); time.sleep(0.02); cmd("stop")
print("CPL0 halt: %s (tries=%d, cpl=%s)" % (got, i, c))

def trial_walk(allproc_addr, limit):
    out = []; p = rdq(allproc_addr); seen = set()
    while is_kptr(p) and p not in seen and len(out) < limit:
        seen.add(p)
        out.append((p, rdw(p + OFF_PID), rdq(p + OFF_TASK)))
        p = rdq(p + OFF_NEXT)
    return out

# 2) find KASLR slide by testing allproc directly: the right slide yields a
#    sane process list (small pids, pid 0/1 present).
slide = None; mapped = 0
for cand in range(0, 0x200000000, 0x200000):
    first = rdq(ALLPROC_S + cand)
    if not is_kptr(first):
        continue
    mapped += 1
    w = trial_walk(ALLPROC_S + cand, 10)
    pids = [x[1] for x in w if x[1] is not None]
    # 10 chained kernel pointers (via le_next), each with a sane small pid at
    # +104, is near-impossible by chance -> that's the real allproc list.
    # (pid 0/1 live at the TAIL since the list inserts at head, so don't require
    #  them here.)
    if len(w) >= 10 and len(pids) >= 10 and all(0 <= x < 200000 for x in pids) and len(set(pids)) >= 6:
        slide = cand; break
print("slide search: mapped-candidates-tested=%d  slide=%s" % (mapped, hex(slide) if slide is not None else "NOT FOUND"))
if slide is None:
    cmd("cont"); s.close(); sys.exit(1)

ALLPROC, KERNPROC = ALLPROC_S + slide, KERNPROC_S + slide
sv = rdq(VM_SLIDE_S + slide)
print("vm_kernel_slide global = %s (expect %s)" % (hex(sv) if sv is not None else "?", hex(slide)))
procs = trial_walk(ALLPROC, 400)

print("\n==== allproc walk: %d procs ====" % len(procs))
for pr, pid, task in procs[:30]:
    print("  proc=%#018x pid=%-6s task=%#x" % (pr, pid, task or 0))
kp = rdq(KERNPROC)
print("kernproc -> %s pid=%s" % (hex(kp) if kp else "?", rdw(kp + OFF_PID) if is_kptr(kp) else "?"))
pids = [x[1] for x in procs if x[1] is not None]
print("\nSUMMARY: %d procs, pids %s..%s, pid0=%s pid1=%s" % (
    len(procs), min(pids) if pids else "?", max(pids) if pids else "?", 0 in pids, 1 in pids))
cmd("cont"); s.close()
