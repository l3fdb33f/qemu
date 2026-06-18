#!/usr/bin/env bash
# Grab a screenshot of the macOS VM via the QEMU monitor and convert to PNG.
#   shot.sh [out.png]   (default ~/macos/shot.png)
MON="$HOME/macos/mac_mon.sock"
OUT="${1:-$HOME/macos/shot.png}"
PPM="/tmp/macshot.ppm"
python3 "$HOME/qemu/tools/macos/mon.py" "$MON" "screendump $PPM" >/dev/null 2>&1
for i in $(seq 1 20); do [ -s "$PPM" ] && break; sleep 0.2; done
python3 - "$PPM" "$OUT" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).save(sys.argv[2])
print("wrote", sys.argv[2])
PY
