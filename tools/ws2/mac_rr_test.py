import sys, os, threading, time
PC = "/Users/eflags/panda-plus/panda-ng/python/core"
sys.path.insert(0, PC)
from pandare2 import Panda

QB   = "/Users/eflags/panda-plus/qemu/build-mac"
BIOS = "/Users/eflags/panda-plus/qemu/pc-bios"
ISO  = "/Users/eflags/panda-plus/vms/alpine-virt.iso"
PLUG = "/Users/eflags/panda-plus/panda-ng/build-mac/plugins"
LOG  = "/tmp/mac_rr_test.log"          # this process's stdout/stderr (panda C prints here too)
RRDIR = "/tmp/macrr"; RR = os.path.join(RRDIR, "a1")
os.makedirs(RRDIR, exist_ok=True)
for f in os.listdir(RRDIR):
    os.remove(os.path.join(RRDIR, f))

BOOT_S  = int(os.environ.get("BOOT_S", "75"))
TARGET  = os.environ.get("TARGET_INSTRS", "20000000")

panda = Panda(
    arch="x86_64", mem="1024",
    os_version="linux-64-alpine",
    expect_prompt=rb"localhost:~#",
    libpanda_path=os.path.join(QB, "libpanda-x86_64-softmmu.dylib"),
    biospath=BIOS, plugin_path=PLUG,
    extra_args=["-L", BIOS, "-accel", "tcg,thread=single",
                "-machine", "pc", "-cpu", "Penryn", "-smp", "1",
                "-drive", f"id=cd0,if=ide,media=cdrom,file={ISO}",
                "-nic", "none", "-display", "none"],
)

def logtail():
    try:
        return open(LOG, "r", errors="ignore").read()
    except Exception:
        return ""

@panda.queue_blocking
def driver():
    print(f"[RR] booting ~{BOOT_S}s before recording...", flush=True)
    time.sleep(BOOT_S)
    print(f"[RR] info rr: {panda.run_monitor_cmd('info rr')}", flush=True)
    print(f"[RR] begin_record {RR} {TARGET} (instruction-bounded, auto-finalizes)", flush=True)
    print("   ->", panda.run_monitor_cmd(f"begin_record {RR} {TARGET}"), flush=True)
    # wait for the bounded segment to finalize
    for _ in range(240):
        time.sleep(0.5)
        if "bounded record complete" in logtail():
            break
    print("[RR] record finalize:", [l for l in logtail().splitlines()
                                     if "bounded record complete" in l or "recording to" in l][-2:], flush=True)
    print("[RR] rr files:", sorted(os.listdir(RRDIR)), flush=True)
    pre = logtail()
    print(f"[RR] begin_replay {RR}", flush=True)
    print("   ->", panda.run_monitor_cmd(f"begin_replay {RR}"), flush=True)
    for _ in range(600):
        time.sleep(1)
        cur = logtail()
        if "RR REPLAY COMPLETE" in cur[len(pre):] or "RR DIVERGENCE" in cur[len(pre):]:
            break
    cur = logtail()[len(pre):]
    div = cur.count("RR DIVERGENCE")
    done = "RR REPLAY COMPLETE" in cur
    print(f"[RR] OUTCOME: replay_complete={done} divergence_count={div}", flush=True)
    markers = [l for l in cur.splitlines() if "RR REPLAY COMPLETE" in l or "RR DIVERGENCE" in l]
    print("[RR] markers:", markers[-3:], flush=True)
    print("RR_PROOF_OK" if (done and div == 0) else "RR_PROOF_CHECK", flush=True)
    os._exit(0)   # avoid the macOS end_analysis teardown hang

print("[RR] starting panda.run()", flush=True)
panda.run()
