#!/usr/bin/env python3
# Validate osi_mac introspection UNDER RR REPLAY.
#  boot (fast, no cb) -> register cb -> live walk (baseline) -> begin_record
#  (bounded) -> begin_replay -> walk DURING replay -> compare to live baseline.
import sys, os, time
import os, sys
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PANDA_QEMU = os.environ.get("PANDA_QEMU", _REPO)
PANDA_PLUGINS = os.environ.get("PANDA_PLUGINS", os.path.expanduser("~/panda-ng"))
MAC = os.environ.get("MACVM", os.path.expanduser("~/macos"))
NG  = PANDA_QEMU + "/build"
PLUG = PANDA_PLUGINS + "/build/plugins"
sys.path.insert(0, PANDA_PLUGINS + "/python/core")
from pandare2 import Panda

RR  = os.path.join(MAC, "rr", "m1r")
OSK = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"

panda = Panda(
    arch="x86_64", mem="4096", os_version="darwin-64-monterey",
    libpanda_path=os.path.join(NG, "libpanda-x86_64-softmmu.so"),
    biospath=PANDA_QEMU + "/pc-bios",
    plugin_path=PLUG,
    extra_args=[
        "-machine","q35","-cpu",
        "Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt",
        "-device", f"isa-applesmc,osk={OSK}",
        "-drive", f"if=pflash,format=raw,readonly=on,file={MAC}/OSX-KVM/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,file={MAC}/mac_vars.fd",
        "-smbios","type=2","-device","ich9-ahci,id=sata",
        "-drive", f"id=OpenCoreBoot,if=none,format=qcow2,file={MAC}/OSX-KVM/OpenCore/OpenCore.qcow2",
        "-device","ide-hd,bus=sata.0,drive=OpenCoreBoot",
        "-drive", f"id=MacHDD,if=none,format=qcow2,file={MAC}/monterey_hdd.qcow2",
        "-device","ide-hd,bus=sata.1,drive=MacHDD",
        "-global","ICH9-LPC.disable_s3=1","-global","ICH9-LPC.disable_s4=1",
        "-usb","-device","qemu-xhci,id=xhci","-device","usb-kbd","-device","usb-tablet",
        "-device","vmware-svga","-nic","none","-display","none",
        "-serial", f"file:{MAC}/osi_replay_serial.log",
    ],
)
panda.load_plugin("osi")
panda.load_plugin("osi_mac")

st = {"phase":"boot", "live":None, "replay":None}

def walk(cpu):
    rows = []
    for p in panda.get_processes(cpu):
        try:
            nm = panda.ffi.string(p.name).decode("utf8","ignore") if p.name != panda.ffi.NULL else "?"
        except Exception:
            nm = "?"
        rows.append((int(p.pid), int(p.ppid), nm))
    return sorted(rows)

def cur_info(cpu):
    cur = panda.get_current_process(cpu)
    if cur == panda.ffi.NULL or cur == 0:
        return None
    nm = panda.ffi.string(cur.name).decode("utf8","ignore") if cur.name != panda.ffi.NULL else "?"
    nmaps = 0
    try:
        maps = panda.plugins["osi"].get_mappings(cpu, cur)
        nmaps = panda.garray_len(maps)
    except Exception:
        pass
    return (int(cur.pid), nm, int(cur.asid), nmaps)

@panda.queue_blocking
def driver():
    print("[drv] booting ~250s (chaining ON, no cb)...", flush=True)
    time.sleep(250)
    print("[drv] registering dump cb post-boot...", flush=True)

    @panda.cb_before_block_exec(name="dump")
    def dump_cb(cpu, tb):
        if not panda.in_kernel(cpu):
            return
        if st["phase"]=="live" and st["live"] is None:
            r = walk(cpu)
            if len(r) >= 5:
                st["live"] = (r, cur_info(cpu))
                print("[LIVE] %d procs, current=%s" % (len(r), st["live"][1]), flush=True)
        elif st["phase"]=="replay" and st["replay"] is None:
            r = walk(cpu)
            if len(r) >= 5:
                st["replay"] = (r, cur_info(cpu))
                print("[REPLAY] %d procs, current=%s" % (len(r), st["replay"][1]), flush=True)

    st["phase"]="live"
    for _ in range(60):
        if st["live"]: break
        time.sleep(1)
    if not st["live"]:
        print("[drv] no live baseline; abort", flush=True); panda.end_analysis(); return

    st["phase"]="record"
    print("[drv] begin_record (bounded 1M):", panda.run_monitor_cmd("begin_record %s 1000000" % RR), flush=True)
    time.sleep(25)   # auto-finalize the bounded segment
    print("[drv] begin_replay:", panda.run_monitor_cmd("begin_replay %s" % RR), flush=True)
    st["phase"]="replay"
    for _ in range(180):
        if st["replay"]: break
        time.sleep(1)
    if not st["replay"]:
        print("[drv] replay walk timed out", flush=True)
    panda.end_analysis()

panda.run()

print("==== RESULT ====", flush=True)
if st["live"] and st["replay"]:
    lp = {(p,n) for p,_,n in st["live"][0]}
    rp = {(p,n) for p,_,n in st["replay"][0]}
    print("live procs=%d replay procs=%d  intersection=%d" % (len(lp), len(rp), len(lp&rp)))
    print("only-live (<=10): ", sorted(lp-rp)[:10])
    print("only-replay (<=10):", sorted(rp-lp)[:10])
    print("live   current:", st["live"][1])
    print("replay current:", st["replay"][1])
    print("MATCH" if lp==rp else "PARTIAL")
else:
    print("MISSING: live=%s replay=%s" % (bool(st["live"]), bool(st["replay"])))
print("[done]", flush=True)
