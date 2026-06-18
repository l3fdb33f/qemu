#!/usr/bin/env python3
# Boot Monterey under panda-ng (libpanda) and validate the XNU ISF by walking
# allproc in kernel context, reading p_pid for each proc.
import sys, os, struct
sys.path.insert(0, os.path.expanduser("~/panda-ng/python/core"))
from pandare2 import Panda

NG  = os.path.expanduser("~/qemu/build")
MAC = os.path.expanduser("~/macos")
OSK = "ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"

# ISF static addresses (KASLR disabled via slide=0) + offsets
ALLPROC   = 0xffffff8000e93770   # struct proclist; lh_first @ +0
KERNPROC  = 0xffffff8000f03a38
VM_SLIDE  = 0xffffff8000e32c90
OFF_NEXT  = 0    # proc.p_list.le_next
OFF_PID   = 104  # proc.p_pid
OFF_TASK  = 16   # proc.task
KBASE     = 0xffffff8000000000

panda = Panda(
    arch="x86_64", mem="4096",
    libpanda_path=os.path.join(NG, "libpanda-x86_64-softmmu.so"),
    biospath=os.path.expanduser("~/qemu/pc-bios"),
    extra_args=[
        "-machine", "q35", "-cpu",
        "Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt",
        "-device", f"isa-applesmc,osk={OSK}",
        "-drive", f"if=pflash,format=raw,readonly=on,file={MAC}/OSX-KVM/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,file={MAC}/mac_vars.fd",
        "-smbios", "type=2",
        "-device", "ich9-ahci,id=sata",
        "-drive", f"id=OpenCoreBoot,if=none,format=qcow2,file={MAC}/OSX-KVM/OpenCore/OpenCore.qcow2",
        "-device", "ide-hd,bus=sata.0,drive=OpenCoreBoot",
        "-drive", f"id=MacHDD,if=none,format=qcow2,file={MAC}/monterey_hdd.qcow2",
        "-device", "ide-hd,bus=sata.1,drive=MacHDD",
        "-global", "ICH9-LPC.disable_s3=1", "-global", "ICH9-LPC.disable_s4=1",
        "-usb", "-device", "qemu-xhci,id=xhci", "-device", "usb-kbd", "-device", "usb-tablet",
        "-device", "vmware-svga", "-nic", "none", "-display", "none",
        "-serial", f"file:{MAC}/walk_serial.log",
    ],
)

state = {"n": 0, "done": False, "tries": 0}

def rd(cpu, addr, n):
    try:
        return bytes(panda.virtual_memory_read(cpu, addr, n))
    except Exception:
        return None

def u64(cpu, addr):
    b = rd(cpu, addr, 8)
    return struct.unpack("<Q", b)[0] if b else None

def u32(cpu, addr):
    b = rd(cpu, addr, 4)
    return struct.unpack("<I", b)[0] if b else None

def is_kptr(v):
    return v is not None and v >= KBASE

@panda.cb_before_block_exec
def bbe(cpu, tb):
    state["n"] += 1
    if state["done"]:
        return
    if state["n"] > 8_000_000_000:
        state["done"] = True
        print("\n[watchdog] block budget exhausted, never found proc list", flush=True)
        panda.end_analysis()
        return
    # give the kernel time to bring up the proc list; throttle attempts
    if state["n"] % 100000 != 0:
        return
    if not panda.in_kernel(cpu):
        return
    first = u64(cpu, ALLPROC)
    if not is_kptr(first):
        return  # kernel not far enough along / not mapped here yet
    state["tries"] += 1
    slide = u64(cpu, VM_SLIDE)
    procs = []
    p = first
    seen = set()
    while is_kptr(p) and p not in seen and len(procs) < 600:
        seen.add(p)
        pid = u32(cpu, p + OFF_PID)
        task = u64(cpu, p + OFF_TASK)
        procs.append((p, pid, task))
        p = u64(cpu, p + OFF_NEXT)
    pids = [x[1] for x in procs]
    if len(procs) >= 3 and any(pid == 1 for pid in pids):
        state["done"] = True
        print("\n==== XNU allproc WALK ====", flush=True)
        print("blocks=%d  vm_kernel_slide=%s" % (state["n"], hex(slide) if slide is not None else "?"), flush=True)
        print("proc count walked: %d" % len(procs), flush=True)
        print("first 25 (proc, pid, task):", flush=True)
        for pr, pid, task in procs[:25]:
            print("  %#018x  pid=%-6s task=%#x" % (pr, pid, task or 0), flush=True)
        kp = u64(cpu, KERNPROC)
        print("kernproc -> %s (pid=%s)" % (hex(kp) if kp else "?", u32(cpu, kp + OFF_PID) if is_kptr(kp) else "?"), flush=True)
        panda.end_analysis()
    elif state["tries"] > 40:
        state["done"] = True
        print("\n[gave up] allproc first=%#x but no sane proc list (tries=%d)" % (first, state["tries"]), flush=True)
        panda.end_analysis()

print("[walk] booting Monterey under panda-ng (slide=0), waiting for kernel proc list...", flush=True)
panda.run()
print("[walk] analysis ended. done=%s" % state["done"], flush=True)
