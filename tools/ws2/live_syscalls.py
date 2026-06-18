import sys, os, threading, time
sys.path.insert(0, os.path.expanduser("~/panda-ng/python/core"))
from pandare2 import Panda

NG   = os.path.expanduser("~/qemu/build")
ISO  = os.path.expanduser("~/alpine-virt.iso")
PLUG = os.path.expanduser("~/panda-ng/build/plugins")

panda = Panda(
    arch="x86_64", mem="1024",
    os_version="linux-64-alpine",
    expect_prompt=rb"localhost:~#",
    libpanda_path=os.path.join(NG, "libpanda-x86_64-softmmu.so"),
    biospath=os.path.expanduser("~/qemu/pc-bios"),
    plugin_path=PLUG,
    extra_args=[
        "-L", os.path.expanduser("~/qemu/pc-bios"),
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

# wall-clock watchdog: end after 60s even if the threshold isn't reached
def watchdog():
    for _ in range(60):
        time.sleep(1)
        if state["done"]:
            return
    if not state["done"]:
        state["done"] = True
        print(f"[PROOF] watchdog timeout; syscalls seen so far: {state['n']}", flush=True)
        try: panda.end_analysis()
        except Exception: pass

threading.Thread(target=watchdog, daemon=True).start()

print("[PROOF] booting Alpine ISO under panda-ng, syscalls2 loaded...", flush=True)
panda.run()

print("==== RESULT ====")
print("total syscall-enter callbacks:", state["n"])
top = sorted(state["nums"].items(), key=lambda kv: -kv[1])[:10]
print("top syscall numbers (callno:count):", top)
print("PROOF_OK" if state["n"] > 0 else "PROOF_FAIL_NO_SYSCALLS")
