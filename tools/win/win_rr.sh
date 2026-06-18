#!/usr/bin/env bash
# Cross-validate device-agnostic RR on Win10 (tiny10) under panda-ng.
#   win_rr.sh [target_instrs] [boot_s] [replay_wait_s]
# Cold-boots tiny10 (MBR/SeaBIOS) under panda-ng TCG single-thread, records a
# bounded mid-boot segment (heavy disk DMA + interrupts), replays it.
set -uo pipefail
source "$(cd "$(dirname "$0")/../.." && pwd)/tools/macos/rr_env.sh"
cd "$WINVM"
Q="$QEMU_BIN"
DISK="$WINVM/win10_test.qcow2"; MON="$WINVM/win_mon.sock"
QLOG="$WINVM/win_qemu.log"; RR="$WINVM/rr/w1"
TARGET="${1:-20000000}"; BOOT="${2:-180}"; WAIT="${3:-600}"
SENT="$WINVM/win_rr.sentinel"
rm -f "$SENT"; exec > "$WINVM/win_rr.log" 2>&1
T(){ python3 "$MON_PY" "$MON" "$1" 2>/dev/null; }

pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$QLOG" "$MON"; rm -rf "$WINVM/rr"; mkdir -p "$WINVM/rr"
echo "=== [$(date)] launch tiny10 under panda-ng ==="
screen -dmS winrr bash -c "$Q -L $PCBIOS -machine pc -accel tcg,thread=single \
  -m 4096 -cpu qemu64 -drive file=$DISK,format=qcow2,if=ide -boot c \
  -monitor unix:$MON,server,nowait -vnc 127.0.0.1:25 -display none -nic none > $QLOG 2>&1"
echo "=== booting ${BOOT}s ==="; sleep "$BOOT"
echo "rr clock after boot: $(T "info rr" | grep -a rr_guest)"
echo "=== bounded record $TARGET ==="
T "begin_record $RR $TARGET"
for i in $(seq 1 240); do grep -qa "bounded record complete" "$QLOG" && break; sleep 0.5; done
grep -a "bounded record complete" "$QLOG" | tail -1
ls -la "$RR"* 2>/dev/null
echo "=== begin_replay ==="
T "begin_replay $RR"
for i in $(seq 1 "$WAIT"); do grep -qaE "RR DIVERGENCE|RR REPLAY COMPLETE" "$QLOG" && break; sleep 1; done
echo "=== OUTCOME (divergence count: $(grep -acE "RR DIVERGENCE" "$QLOG")) ==="
grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$QLOG" | tail -2 || echo "<none>"
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
