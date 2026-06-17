#!/usr/bin/env bash
# Record+replay an INSTRUCTION-BOUNDED Monterey segment under panda-ng RR.
#   mac_rr.sh [target_instrs] [replay_wait_s]
# Boots Monterey (screen), then `begin_record <name> <target_instrs>` which
# auto-finalizes the recording the moment the guest instruction count crosses
# the cap (no stop/cont wall-clock window -- precise, small, reproducible
# segment for divergence debugging). Then begin_replay, watch for
# RR REPLAY COMPLETE / RR DIVERGENCE. Output -> ~/macos/mac_rr.log.
set -uo pipefail
cd "$HOME/macos"
L="$HOME/macos/mac_launch.log"; MON="$HOME/macos/mac_mon.sock"; RR="$HOME/macos/rr/m1"
TARGET="${1:-5000000}"; WAIT="${2:-1800}"
SENT="$HOME/macos/mac_rr.sentinel"
rm -f "$SENT"; exec > "$HOME/macos/mac_rr.log" 2>&1
T(){ python3 "$HOME/panda-ng/tools/macos/mon.py" "$MON" "$1" 2>/dev/null; }
rrcount(){ T "info rr" | grep -a rr_guest | grep -oE '[0-9]+' | tail -1; }

echo "=== [$(date)] launch qemu under screen ==="
pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"; rm -rf "$HOME/macos/rr"; mkdir -p "$HOME/macos/rr"
screen -dmS mac bash -c "$HOME/macos/mac_run.sh tcg > $L 2>&1"

echo "=== wait for boot ==="
for i in $(seq 1 400); do
  grep -qa "IOConsoleUsers\|gIOScreenLockState" mac_serial.log 2>/dev/null && break
  sleep 1
done
echo "booted after ~${i}s; free-running rr clock: $(rrcount)"
sleep 5

echo "=== [$(date)] instruction-bounded record: begin_record $RR $TARGET (auto-stops at cap) ==="
T "begin_record $RR $TARGET"
# The engine snapshots at count 0 and auto-finalizes once it crosses the cap.
for i in $(seq 1 240); do
  grep -qa "bounded record complete" "$L" && break
  sleep 0.5
done
echo "--- record finalize line ---"
grep -a "bounded record complete\|RR: recording to" "$L" | tail -2
ls -la "$RR"* 2>/dev/null
NONDET="$RR-rr-nondet.log"
echo "nondet log size: $(stat -c%s "$NONDET" 2>/dev/null) bytes"
sleep 1

echo "=== [$(date)] begin_replay ==="
RSTART=$(date +%s)
T "begin_replay $RR"
for i in $(seq 1 "$WAIT"); do
  grep -qaE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" && break
  sleep 1
done
RELAPSED=$(( $(date +%s) - RSTART ))
echo "=== [$(date)] OUTCOME (after ${i}s replay wait) ==="
grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" | head -2 || echo "<none / still running>"
RC=$(rrcount)
echo "=== replay rr clock: $RC  (elapsed ${RELAPSED}s ~= $(( RC / (RELAPSED>0?RELAPSED:1) )) instr/s) ==="
echo "=== RR-related log tail ==="
grep -aiE "RR:|REPLAY|DIVERGENCE|pull|nondet|rr_|bounded" "$L" | tail -20
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
