#!/usr/bin/env bash
# Set OpenCore NVRAM boot-args in OSX-KVM/OpenCore/OpenCore.qcow2.
#   set_bootargs.sh "<boot-args string>"
set -e
cd "$HOME/macos"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
RAW=/tmp/oc_edit.raw
PL=/tmp/oc_edit.plist
QIMG="$HOME/qemu/build/qemu-img"
ARGS="$1"

"$QIMG" convert -O raw "$OC" "$RAW"
mcopy -o -i "$RAW@@1048576" ::/EFI/OC/config.plist "$PL"
python3 - "$PL" "$ARGS" <<'PY'
import plistlib, sys
p, args = sys.argv[1], sys.argv[2]
c = plistlib.load(open(p, "rb"))
nv = c.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(
    "7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
print("old boot-args:", repr(nv.get("boot-args")))
nv["boot-args"] = args
plistlib.dump(c, open(p, "wb"))
print("new boot-args:", repr(args))
PY
mcopy -o -i "$RAW@@1048576" "$PL" ::/EFI/OC/config.plist
"$QIMG" convert -f raw -O qcow2 "$RAW" "$OC"
echo "OpenCore rebuilt with new boot-args"
