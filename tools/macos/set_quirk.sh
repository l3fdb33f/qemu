#!/usr/bin/env bash
# Enable OpenCore Booter quirks needed to honor slide=0 (disable KASLR) on OVMF.
set -e
cd "$HOME/macos"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
RAW=/tmp/ocq.raw; PL=/tmp/ocq.plist
QIMG="$HOME/qemu/build/qemu-img"
"$QIMG" convert -O raw "$OC" "$RAW"
mcopy -o -i "$RAW@@1048576" ::/EFI/OC/config.plist "$PL"
python3 - "$PL" <<'PY'
import plistlib, sys
c = plistlib.load(open(sys.argv[1], "rb"))
q = c["Booter"]["Quirks"]
for k in ["ProvideCustomSlide", "SetupVirtualMap"]:
    print("%s: %s -> True" % (k, q.get(k))); q[k] = True
plistlib.dump(c, open(sys.argv[1], "wb"))
PY
mcopy -o -i "$RAW@@1048576" "$PL" ::/EFI/OC/config.plist
"$QIMG" convert -f raw -O qcow2 "$RAW" "$OC"
echo "OpenCore quirks updated"
