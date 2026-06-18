#!/usr/bin/env bash
# Revert OpenCore to the known-good auto-booting config (KASLR on): the slide=0
# path isn't usable on this OVMF memmap. Drop slide=0, restore quirks, reset NVRAM.
set -e
cd "$HOME/macos"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
RAW=/tmp/ocr.raw; PL=/tmp/ocr.plist
QIMG="$HOME/qemu/build/qemu-img"
"$QIMG" convert -O raw "$OC" "$RAW"
mcopy -o -i "$RAW@@1048576" ::/EFI/OC/config.plist "$PL"
python3 - "$PL" <<'PY'
import plistlib, sys
c = plistlib.load(open(sys.argv[1], "rb"))
q = c["Booter"]["Quirks"]
q["ProvideCustomSlide"] = False
q["SetupVirtualMap"] = False
nv = c["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
nv["boot-args"] = "-v keepsyms=1 debug=0x100 serial=1"
print("reverted: PCS=False SVM=False boot-args=%r" % nv["boot-args"])
plistlib.dump(c, open(sys.argv[1], "wb"))
PY
mcopy -o -i "$RAW@@1048576" "$PL" ::/EFI/OC/config.plist
"$QIMG" convert -f raw -O qcow2 "$RAW" "$OC"
rm -f "$HOME/macos/mac_vars.fd"
echo "reverted to known-good config + NVRAM reset"
