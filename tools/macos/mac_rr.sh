#!/usr/bin/env bash
# Record+replay a SHORT Monterey segment under panda-ng device-agnostic RR.
#   mac_rr.sh [target_instrs] [replay_wait_s]
# Boots Monterey (screen), records until ~target_instrs, end_record, begin_replay,
# watches for RR REPLAY COMPLETE / RR DIVERGENCE. Output -> ~/macos/mac_rr.log.
set -uo pipefail
cd "$HOME/macos"
L="$HOME/macos/mac_launch.log"; MON="$HOME/macos/mac_mon.sock"; RR="$HOME/macos/rr/m1"
REC_SECS="${1:-0.5}"; WAIT="${2:-900}"
SENT="$HOME/macos/mac_rr.sentinel"
rm -f "$SENT"; exec > "$HOME/macos/mac_rr.log" 2>&1
T(){ python3 "$HOME/panda-ng/tools/macos/mon.py" "$MON" "$1" 2>/dev/null; }
rrcount(){ T "info rr" | grep -a rr_guest | grep -oE '[0-9]+' | tail -1; }

echo "=== [$(date)] launch qemu under screen ==="
pkill -9 qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"; rm -rf "$HOME/macos/rr"; mkdir -p "$HOME/macos/rr"
screen -dmS mac bash -c "$HOME/macos/mac_run.sh tcg > $L 2>&1"

echo "=== wait for boot ==="
for i in $(seq 1 400); do
  grep -qa "IOConsoleUsers\|gIOScreenLockState" mac_serial.log 2>/dev/null && break
  sleep 1
done
echo "booted after ~${i}s; free-running rr clock: $(rrcount)"
sleep 5

echo "=== [$(date)] bounded record: stop -> begin_record -> brief cont -> stop ==="
T "stop"                      # freeze the guest so the segment is bounded
T "begin_record $RR"
START=$(rrcount); echo "start count (frozen): $START"
T "cont"                      # run a brief window
sleep "${REC_SECS:-0.5}"
T "stop"
END=$(rrcount); echo "recorded segment: $START -> $END  (~$((END - START)) instr)"
echo "--- end_record ---"; T "end_record"
ls -la "$RR"* 2>/dev/null
sleep 1

echo "=== [$(date)] begin_replay ==="
T "begin_replay $RR"
for i in $(seq 1 "$WAIT"); do
  grep -qaE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" && break
  sleep 1
done
echo "=== [$(date)] OUTCOME (after ${i}s replay wait) ==="
grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" | head -2 || echo "<none / still running>"
echo "=== replay rr clock: $(rrcount) ==="
echo "=== RR-related log tail ==="
grep -aiE "RR:|REPLAY|DIVERGENCE|pull|nondet|rr_" "$L" | tail -15
pkill -9 qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
