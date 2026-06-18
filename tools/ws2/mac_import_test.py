import sys, os
PC = "/Users/eflags/panda-plus/panda-ng/python/core"
sys.path.insert(0, PC)
try:
    from pandare2 import Panda
    print("IMPORT_OK")
except Exception:
    import traceback; traceback.print_exc(); print("IMPORT_FAIL"); sys.exit(1)

QB = "/Users/eflags/panda-plus/qemu/build-mac"
LIB = os.path.join(QB, "libpanda-x86_64-softmmu.dylib")
BIOS = "/Users/eflags/panda-plus/qemu/pc-bios"
PLUG = "/Users/eflags/panda-plus/panda-ng/build-mac/plugins"
try:
    panda = Panda(
        arch="x86_64", mem="1024",
        expect_prompt=rb"localhost:~#",
        libpanda_path=LIB, biospath=BIOS, plugin_path=PLUG,
        raw_monitor=False,
        extra_args=["-L", BIOS, "-accel", "tcg,thread=single",
                    "-machine", "pc", "-cpu", "Penryn", "-smp", "1",
                    "-nic", "none", "-display", "none"],
    )
    print("CONSTRUCT_OK libpanda=", panda.libpanda_path)
    print("arch_name=", panda.arch_name, "bits=", panda.bits, "os_type=", panda.os_type)
except Exception:
    import traceback; traceback.print_exc(); print("CONSTRUCT_FAIL"); sys.exit(2)
