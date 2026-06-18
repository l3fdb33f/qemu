import sys, os, time
PC = "/Users/eflags/panda-plus/panda-ng/python/core"
sys.path.insert(0, PC)
from pandare2 import Panda

QB    = "/Users/eflags/panda-plus/qemu/build-mac"
BIOS  = "/Users/eflags/panda-plus/qemu/pc-bios"
PLUG  = "/Users/eflags/panda-plus/panda-ng/build-mac/plugins"
QCOW  = "/Users/eflags/panda-plus/vms/base/ubuntu_configured.qcow2"
KCONF = "/Users/eflags/pandbox/data/linux/ubuntu-noble-kernelinfo.conf"
KGROUP = "ubuntu:6.8.0-117-generic:64"
LOG   = "/tmp/mac_osi_linux_test.log"
RRDIR = "/tmp/macosi"; RR = os.path.join(RRDIR, "u1")
os.makedirs(RRDIR, exist_ok=True)
for f in os.listdir(RRDIR):
    os.remove(os.path.join(RRDIR, f))

BOOT_S = int(os.environ.get("BOOT_S", "150"))
TARGET = os.environ.get("TARGET_INSTRS", "20000000")

panda = Panda(
    arch="x86_64", mem="1024",
    os_version="linux-64-ubuntu:6.8.0-117-generic",
    qcow=QCOW,
    libpanda_path=os.path.join(QB, "libpanda-x86_64-softmmu.dylib"),
    biospath=BIOS, plugin_path=PLUG,
    extra_args=["-L", BIOS, "-accel", "tcg,thread=single",
                "-machine", "pc", "-cpu", "Penryn", "-smp", "1",
                "-nic", "none", "-display", "none"],
)

# Mirror PANDBox: osi (no autoload) + osi_linux with the Noble kernelinfo.
panda.load_plugin("osi", {"disable-autoload": "true"})
panda.load_plugin("osi_linux", {"kconf_file": KCONF, "kconf_group": KGROUP})

st = {"phase": "boot", "live": None, "replay": None}

def logread():
    try: return open(LOG, "r", errors="ignore").read()
    except Exception: return ""

def walk(cpu):
    rows = []
    try:
        for p in panda.get_processes(cpu):
            nm = panda.ffi.string(p.name).decode("utf8", "ignore") if p.name != panda.ffi.NULL else "?"
            rows.append((int(p.pid), int(p.ppid), nm))
    except Exception as e:
        print("[walk] error:", e, flush=True)
    return sorted(rows)

def cur(cpu):
    c = panda.get_current_process(cpu)
    if c == panda.ffi.NULL or c == 0: return None
    nm = panda.ffi.string(c.name).decode("utf8", "ignore") if c.name != panda.ffi.NULL else "?"
    return (int(c.pid), nm, int(c.asid))

@panda.cb_before_block_exec(name="osi_walk")
def osi_walk(cpu, tb):
    if not panda.in_kernel(cpu):
        return
    if st["phase"] == "live" and st["live"] is None:
        r = walk(cpu)
        if len(r) >= 5:
            st["live"] = (r, cur(cpu))
            print(f"[LIVE] {len(r)} procs, current={st['live'][1]}", flush=True)
            print("[LIVE] sample:", st["live"][0][:12], flush=True)
    elif st["phase"] == "replay" and st["replay"] is None:
        r = walk(cpu)
        if len(r) >= 5:
            st["replay"] = (r, cur(cpu))
            print(f"[REPLAY] {len(r)} procs, current={st['replay'][1]}", flush=True)

@panda.queue_blocking
def driver():
    print(f"[OSI] cold-booting Noble ~{BOOT_S}s (kernel 6.8.0-117)...", flush=True)
    time.sleep(BOOT_S)
    print("[OSI] phase=live; walking processes via osi_linux...", flush=True)
    st["phase"] = "live"
    for _ in range(60):
        if st["live"]: break
        time.sleep(1)
    if not st["live"]:
        print("[OSI] LIVE walk failed (osi_linux could not enumerate). PROOF_FAIL", flush=True)
        os._exit(0)
    # record a bounded segment, then replay and walk again
    st["phase"] = "record"
    print(f"[OSI] begin_record {RR} {TARGET}", panda.run_monitor_cmd(f"begin_record {RR} {TARGET}"), flush=True)
    for _ in range(240):
        time.sleep(0.5)
        if "bounded record complete" in logread(): break
    print("[OSI] record done:", [l for l in logread().splitlines() if "bounded record complete" in l][-1:], flush=True)
    pre = logread()
    print(f"[OSI] begin_replay {RR}", panda.run_monitor_cmd(f"begin_replay {RR}"), flush=True)
    st["phase"] = "replay"
    for _ in range(600):
        time.sleep(1)
        if st["replay"]: break
        if "RR REPLAY COMPLETE" in logread()[len(pre):] or "RR DIVERGENCE" in logread()[len(pre):]:
            break
    div = logread()[len(pre):].count("RR DIVERGENCE")
    print("==== RESULT ====", flush=True)
    print(f"live procs={len(st['live'][0])} current={st['live'][1]}", flush=True)
    if st["replay"]:
        print(f"replay procs={len(st['replay'][0])} current={st['replay'][1]}", flush=True)
    print(f"replay_divergence={div}", flush=True)
    ok = st["live"] and len(st["live"][0]) >= 5
    print("OSI_PROOF_OK" if ok else "OSI_PROOF_FAIL", flush=True)
    os._exit(0)

print("[OSI] starting panda.run()", flush=True)
panda.run()
