#!/usr/bin/env python3
# Validate the osi_mac plugin live: load osi + osi_mac, boot Monterey under
# panda-ng (full speed, no per-block cb), then call get_processes in a CPL0 halt.
import sys, os, time, re
import os, sys
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PANDA_QEMU = os.environ.get("PANDA_QEMU", _REPO)
PANDA_PLUGINS = os.environ.get("PANDA_PLUGINS", os.path.expanduser("~/panda-ng"))
MAC = os.environ.get("MACVM", os.path.expanduser("~/macos"))
NG  = PANDA_QEMU + "/build"
PLUG = PANDA_PLUGINS + "/build/plugins"
sys.path.insert(0, PANDA_PLUGINS + "/python/core")
from pandare2 import Panda

OSK = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"

panda = Panda(
    arch="x86_64", mem="4096",
    os_version="darwin-64-monterey", # OS_DARWIN family (added to panda-ng core)
    libpanda_path=os.path.join(NG, "libpanda-x86_64-softmmu.so"),
    biospath=PANDA_QEMU + "/pc-bios",
    plugin_path=PLUG,
    extra_args=[
        "-machine", "q35", "-cpu",
        "Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt",
        "-device", f"isa-applesmc,osk={OSK}",
        "-drive", f"if=pflash,format=raw,readonly=on,file={MAC}/OSX-KVM/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,file={MAC}/mac_vars.fd",
        "-smbios", "type=2", "-device", "ich9-ahci,id=sata",
        "-drive", f"id=OpenCoreBoot,if=none,format=qcow2,file={MAC}/OSX-KVM/OpenCore/OpenCore.qcow2",
        "-device", "ide-hd,bus=sata.0,drive=OpenCoreBoot",
        "-drive", f"id=MacHDD,if=none,format=qcow2,file={MAC}/monterey_hdd.qcow2",
        "-device", "ide-hd,bus=sata.1,drive=MacHDD",
        "-global", "ICH9-LPC.disable_s3=1", "-global", "ICH9-LPC.disable_s4=1",
        "-usb", "-device", "qemu-xhci,id=xhci", "-device", "usb-kbd", "-device", "usb-tablet",
        "-device", "vmware-svga", "-nic", "none", "-display", "none",
        "-serial", f"file:{MAC}/osi_serial.log",
    ],
)
panda.load_plugin("osi")
panda.load_plugin("osi_mac")

state = {"done": False}

def do_dump(cpu):
    if state["done"] or not panda.in_kernel(cpu):
        return
    procs = panda.get_processes(cpu)
    rows = []
    for p in procs:
        try:
            nm = panda.ffi.string(p.name).decode("utf8", "ignore") if p.name != panda.ffi.NULL else "?"
        except Exception:
            nm = "?"
        rows.append((int(p.pid), int(p.ppid), nm))
    if len(rows) < 5:
        return  # not fully booted yet
    state["done"] = True
    print("[test] osi_mac get_processes returned %d procs" % len(rows), flush=True)
    for pid, ppid, nm in sorted(rows)[:45]:
        print("  pid=%-5d ppid=%-5d %s" % (pid, ppid, nm), flush=True)
    try:
        cur = panda.get_current_process(cpu)
        if cur != panda.ffi.NULL and cur != 0:
            cnm = panda.ffi.string(cur.name).decode("utf8", "ignore") if cur.name != panda.ffi.NULL else "?"
            print("[test] current process: pid=%d ppid=%d name=%s asid=0x%x" % (
                int(cur.pid), int(cur.ppid), cnm, int(cur.asid)), flush=True)
        else:
            print("[test] current process: NULL", flush=True)
    except Exception as e:
        print("[test] get_current_process error:", e, flush=True)
    # current thread (via the new pandare2 wrapper)
    try:
        t = panda.get_current_thread(cpu)
        if t is not None:
            print("[test] current thread: pid=%d tid=%d" % (int(t.pid), int(t.tid)), flush=True)
    except Exception as e:
        print("[test] get_current_thread error:", e, flush=True)
    # kernel extensions (read names DURING iteration; cleanup frees them after)
    try:
        cnt = 0
        names = []
        for m in panda.get_modules(cpu):
            if cnt < 12:
                names.append(panda.ffi.string(m.name).decode("utf8", "ignore") if m.name != panda.ffi.NULL else "?")
            cnt += 1
        print("[test] get_modules returned %d kexts; first 12: %s" % (cnt, names), flush=True)
    except Exception as e:
        print("[test] get_modules error:", e, flush=True)
    # process memory regions (on_get_mappings) for the current process
    try:
        if cur != panda.ffi.NULL and cur != 0:
            maps = panda.plugins["osi"].get_mappings(cpu, cur)
            nmaps = panda.garray_len(maps)
            print("[test] get_mappings(current) -> %d regions; first 8:" % nmaps, flush=True)
            for i in range(min(nmaps, 8)):
                mm = panda.plugins["osi"].get_one_module(maps, i)
                print("    base=0x%-12x size=0x%x" % (int(mm.base), int(mm.size)), flush=True)
    except Exception as e:
        print("[test] get_mappings error:", e, flush=True)
    panda.end_analysis()

@panda.queue_blocking
def driver():
    # Boot FULL SPEED with no callback registered (chaining stays on), then
    # register before_block_exec post-boot so the chaining penalty only applies
    # after the guest is up (a few blocks until kernel ctx -> instant).
    print("[test] booting Monterey ~250s (full speed, no cb)...", flush=True)
    time.sleep(250)
    print("[test] registering dump callback post-boot...", flush=True)
    @panda.cb_before_block_exec(name="dump")
    def dump_cb(cpu, tb):
        do_dump(cpu)
    for _ in range(180):
        if state["done"]:
            break
        time.sleep(1)
    if not state["done"]:
        print("[test] timed out", flush=True)
    panda.end_analysis()

panda.run()
print("[test] done", flush=True)
