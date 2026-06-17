import sys, os
sys.path.insert(0, os.path.expanduser("~/panda-ng-plugins/python/core"))
try:
    from pandare2 import Panda
    print("IMPORT_OK")
except Exception as e:
    import traceback; traceback.print_exc(); print("IMPORT_FAIL"); sys.exit(1)

NG = os.path.expanduser("~/panda-ng/build")
ISO = os.path.expanduser("~/alpine-virt.iso")
PLUG = os.path.expanduser("~/panda-ng-plugins/build/plugins")
try:
    panda = Panda(
        arch="x86_64",
        mem="1024",
        expect_prompt=rb"localhost:~#",
        libpanda_path=os.path.join(NG, "libpanda-x86_64-softmmu.so"),
        biospath=os.path.join(NG, "pc-bios"),
        plugin_path=PLUG,
        raw_monitor=False,
        extra_args=[
            "-L", os.path.join(NG, "pc-bios"),
            "-accel", "tcg,thread=single",
            "-machine", "pc", "-cpu", "Penryn", "-smp", "1",
            "-drive", f"id=cd0,if=ide,media=cdrom,file={ISO}",
            "-nic", "none", "-display", "none",
        ],
    )
    print("CONSTRUCT_OK libpanda=", panda.libpanda_path)
    print("plugin_path=", panda.plugin_path)
except Exception as e:
    import traceback; traceback.print_exc(); print("CONSTRUCT_FAIL"); sys.exit(2)
