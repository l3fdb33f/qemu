#!/usr/bin/env bash
# slide=0 needs ProvideCustomSlide=True; SetupVirtualMap=True broke OpenCore on
# this OVMF, so force it False. Also reset OVMF NVRAM (clear stale boot entry).
set -e
cd "$HOME/macos"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
RAW=/tmp/ocf.raw; PL=/tmp/ocf.plist
QIMG="$HOME/panda-ng/build/qemu-img"
"$QIMG" convert -O raw "$OC" "$RAW"
mcopy -o -i "$RAW@@1048576" ::/EFI/OC/config.plist "$PL"
python3 - "$PL" <<'PY'
import plistlib, sys
c = plistlib.load(open(sys.argv[1], "rb"))
q = c["Booter"]["Quirks"]
q["ProvideCustomSlide"] = True
q["SetupVirtualMap"] = False
print("ProvideCustomSlide=True, SetupVirtualMap=False")
plistlib.dump(c, open(sys.argv[1], "wb"))
PY
mcopy -o -i "$RAW@@1048576" "$PL" ::/EFI/OC/config.plist
"$QIMG" convert -f raw -O qcow2 "$RAW" "$OC"
rm -f "$HOME/macos/mac_vars.fd"   # fresh OVMF NVRAM next boot
echo "quirks fixed + NVRAM reset"
