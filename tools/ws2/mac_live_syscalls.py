import sys, os, threading, time
PC = "/Users/eflags/panda-plus/panda-ng/python/core"
sys.path.insert(0, PC)
from pandare2 import Panda

QB   = "/Users/eflags/panda-plus/qemu/build-mac"
BIOS = "/Users/eflags/panda-plus/qemu/pc-bios"
ISO  = "/Users/eflags/panda-plus/vms/alpine-virt.iso"
PLUG = "/Users/eflags/panda-plus/panda-ng/build-mac/plugins"

panda = Panda(
    arch="x86_64", mem="1024",
    os_version="linux-64-alpine",
    expect_prompt=rb"localhost:~#",
    libpanda_path=os.path.join(QB, "libpanda-x86_64-softmmu.dylib"),
    biospath=BIOS,
    plugin_path=PLUG,
    extra_args=[
        "-L", BIOS,
        "-accel", "tcg,thread=single",
        "-machine", "pc", "-cpu", "Penryn", "-smp", "1",
        "-drive", f"id=cd0,if=ide,media=cdrom,file={ISO}",
        "-nic", "none", "-display", "none",
    ],
)

state = {"n": 0, "nums": {}, "done": False}

@panda.ppp("syscalls2", "on_all_sys_enter")
def on_sys_enter(cpu, pc, callno):
    state["n"] += 1
    state["nums"][callno] = state["nums"].get(callno, 0) + 1
    if state["n"] == 1:
        print(f"[PROOF] first syscall observed: callno={callno} pc={pc:#x}", flush=True)
    if state["n"] >= 20000 and not state["done"]:
        state["done"] = True
        print(f"[PROOF] reached {state['n']} syscalls, ending analysis", flush=True)
        panda.end_analysis()

def watchdog():
    for _ in range(300):
        time.sleep(1)
        if state["done"]:
            return
    if not state["done"]:
        state["done"] = True
        print(f"[PROOF] watchdog timeout; syscalls seen so far: {state['n']}", flush=True)
        try: panda.end_analysis()
        except Exception: pass

threading.Thread(target=watchdog, daemon=True).start()

print("[PROOF] booting Alpine ISO under panda-ng (macOS arm64, TCG x86_64), syscalls2 loaded...", flush=True)
panda.run()

print("==== RESULT ====")
print("total syscall-enter callbacks:", state["n"])
top = sorted(state["nums"].items(), key=lambda kv: -kv[1])[:10]
print("top syscall numbers (callno:count):", top)
print("PROOF_OK" if state["n"] > 0 else "PROOF_FAIL_NO_SYSCALLS")
