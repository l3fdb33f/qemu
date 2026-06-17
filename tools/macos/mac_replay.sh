#!/usr/bin/env bash
# FAST replay-only iteration: relaunch qemu and begin_replay the SAVED recording
# (rr/m1) WITHOUT waiting for macOS to boot -- loadvm overwrites guest state, so
# replay works from the OpenCore picker. ~15s/iteration vs ~150s full boot.
#   mac_replay.sh [replay_wait_s]
set -uo pipefail
cd "$HOME/macos"
L="$HOME/macos/mac_launch.log"; MON="$HOME/macos/mac_mon.sock"; RR="$HOME/macos/rr/m1"
WAIT="${1:-120}"
SENT="$HOME/macos/mac_replay.sentinel"
rm -f "$SENT"; exec > "$HOME/macos/mac_replay.log" 2>&1
T(){ python3 "$HOME/panda-ng/tools/macos/mon.py" "$MON" "$1" 2>/dev/null; }

echo "=== [$(date)] launch qemu ==="
pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"
screen -dmS mac bash -c "$HOME/macos/mac_run.sh tcg > $L 2>&1"

echo "=== wait for monitor socket (NOT full boot) ==="
for i in $(seq 1 60); do [ -S "$MON" ] && break; sleep 1; done
sleep 3
echo "monitor up after ~${i}s"

echo "=== [$(date)] begin_replay $RR ==="
T "begin_replay $RR"
for i in $(seq 1 "$WAIT"); do
  grep -qaE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" && break
  sleep 1
done
echo "=== [$(date)] OUTCOME (after ${i}s) ==="
grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" | tail -1 || echo "<none>"
echo "=== loaded entries line ==="
grep -a "loaded .* nondet log entries" "$L" | tail -1
echo "=== probe trace (RRINJ/RRMISS/RRAPPR) — last 120 ==="
grep -aE "RRINJ|RRMISS|RRAPPR" "$L" | tail -120
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
