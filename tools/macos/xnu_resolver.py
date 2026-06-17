#!/usr/bin/env python3
# Robust XNU resolver for Monterey-under-panda-ng: locates the live kernelcache
# header, derives runtime segment bases, rebases dSYM symbols per-segment
# (handles per-boot KC slide), and walks allproc -> (pid, ppid, name).
import socket, time, re, os, sys

SOCK = os.path.expanduser("~/macos/mac_mon.sock")
KBASE = 0xffffff8000000000

# dSYM (KDK 21G115) segment bases -> (vmaddr, size). Fixed for this kernel.
DSYM_SEGS = {
    "__HIB":        (0xffffff8000100000, 0xa0000),
    "__TEXT":       (0xffffff8000200000, 0xa00000),
    "__DATA":       (0xffffff8000c00000, 0x297000),
    "__DATA_CONST": (0xffffff8000e97000, 0x88000),
}
# symbols of interest (static dSYM addrs from the ISF)
SYM = {"allproc": 0xffffff8000e93770, "kernproc": 0xffffff8000f03a38,
       "vm_kernel_slide": 0xffffff8000e32c90}
OFF = {"next": 0, "task": 16, "ppid": 40, "pid": 104, "comm": 1029}

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
def rdbytes(a, n):
    r = cmd("x/%dbx 0x%x" % (n, a))
    return bytes(int(x,16) for x in re.findall(r"\b0x([0-9a-fA-F]{2})\b", r))
def isk(v): return v is not None and v>=KBASE

# 1+2) acquire a halt where kernel __TEXT is mapped (full kernel CR3, not the
#      KPTI trampoline's user CR3) and locate the live KC header.
#      Fast path: probe likely header VAs; fall back to a wide scan.
GUESSES = [0xffffff8005a00000]
def find_kc():
    for g in GUESSES:
        if rdw(g) == 0xfeedfacf and rdw(g+12) == 0xc:
            return g
    return None
kc = None
for attempt in range(60):
    cmd("stop")
    if cpl() != 0:
        cmd("cont"); time.sleep(0.02); continue
    kc = find_kc()
    if kc:
        break
    cmd("cont"); time.sleep(0.03)
if kc is None:
    # KC not at a guessed VA on any good halt -> wide scan (handles KC slide)
    print("guess failed; wide-scanning for KC header...")
    for attempt in range(20):
        cmd("stop")
        if cpl() != 0:
            cmd("cont"); time.sleep(0.02); continue
        for a in range(0xffffff8004000000, 0xffffff8030000000, 0x200000):
            if rdw(a) == 0xfeedfacf and rdw(a+12) == 0xc:
                kc = a; break
        if kc: break
        cmd("cont"); time.sleep(0.05)
if kc is None:
    print("KC header not found"); cmd("cont"); sys.exit(1)
print("KC header @ 0x%x (ncmds=%d, attempt=%d)" % (kc, rdw(kc+16), attempt))

# 3) parse KC runtime segment bases
kc_segs = {}
ncmds = rdw(kc+16); off = kc+32
for _ in range(ncmds):
    ct, cs = rdw(off), rdw(off+4)
    if not cs: break
    if ct == 0x19:
        raw = rdbytes(off+8,16)
        m = re.search(rb"__[A-Z0-9_]+", raw)
        nm = m.group().decode() if m else raw.split(b"\x00")[0].decode(errors="replace")
        kc_segs[nm] = rdq(off+24)
    off += cs
print("KC segs:", {k: hex(v) for k,v in kc_segs.items() if k in DSYM_SEGS})

def resolve(static):
    for nm,(base,size) in DSYM_SEGS.items():
        if base <= static < base+size and nm in kc_segs:
            return static - base + kc_segs[nm]
    return None

allproc = resolve(SYM["allproc"])
kernproc = resolve(SYM["kernproc"])
print("rebased: allproc=0x%x  kernproc=0x%x" % (allproc, kernproc))
kp = rdq(kernproc)
print("kernproc deref -> %s (pid %s)" % (hex(kp) if kp else "?", rdw(kp+OFF["pid"]) if isk(kp) else "?"))

# 4) walk allproc, full named list
def name(proc):
    # robust: longest printable run in the p_comm(+1029)/p_name(+1046) window
    b = rdbytes(proc+1020, 64)
    runs = re.findall(rb"[ -~]{2,}", b)
    return max(runs, key=len).decode(errors="replace") if runs else "?"
rows=[]; p=rdq(allproc); seen=set()
while isk(p) and p not in seen and len(rows)<600:
    seen.add(p)
    rows.append((rdw(p+OFF["pid"]), rdw(p+OFF["ppid"]), name(p), p))
    p = rdq(p+OFF["next"])
cmd("cont"); s.close()
rows.sort(key=lambda r:(r[0] if r[0] is not None else 1<<31))
print("\n==== %d procs ====" % len(rows))
print("  PID   PPID  COMMAND")
for pid,ppid,nm,pr in rows:
    print("  %-5s %-5s %s" % (pid, ppid, nm))
