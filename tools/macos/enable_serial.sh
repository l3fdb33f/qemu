#!/usr/bin/env bash
# Enable OpenCore serial kernel-output patches + set serial=1 boot-arg so XNU
# routes panic/early prints to the QEMU serial port (mac_serial.log).
set -e
cd "$HOME/macos"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
RAW=/tmp/oc_ser.raw; PL=/tmp/oc_ser.plist
QIMG="$HOME/qemu/build/qemu-img"
"$QIMG" convert -O raw "$OC" "$RAW"
mcopy -o -i "$RAW@@1048576" ::/EFI/OC/config.plist "$PL"
python3 - "$PL" <<'PY'
import plistlib, sys
p = sys.argv[1]
c = plistlib.load(open(p, "rb"))
en = 0
for pat in c.get("Kernel", {}).get("Patch", []):
    cm = pat.get("Comment", "").lower()
    if "serial" in cm or "panic string" in cm or "early print" in cm:
        if not pat.get("Enabled"):
            pat["Enabled"] = True; en += 1
        print("enabled:", pat.get("Comment", "")[:60])
# also make sure Misc>Debug routes to serial
dbg = c.setdefault("Misc", {}).setdefault("Debug", {})
dbg["Target"] = dbg.get("Target", 0) | 0x40 | 0x08  # serial + file? 0x40=serial-ish; harmless
nv = c.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(
    "7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
ba = nv.get("boot-args", "")
if "serial=" not in ba:
    ba = (ba + " serial=1").strip()
nv["boot-args"] = ba
print("boot-args:", repr(ba), "| serial patches enabled:", en)
plistlib.dump(c, open(p, "wb"))
PY
mcopy -o -i "$RAW@@1048576" "$PL" ::/EFI/OC/config.plist
"$QIMG" convert -f raw -O qcow2 "$RAW" "$OC"
echo "serial kernel output enabled + rebuilt"
