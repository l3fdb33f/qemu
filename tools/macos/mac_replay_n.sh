#!/usr/bin/env bash
# Replay the SAVED recording N times in ONE qemu launch to test determinism:
# begin_replay -> outcome -> end_replay, repeated. If the divergence count
# varies across identical runs, replay has live (async) nondeterminism.
#   mac_replay_n.sh [N] [per_wait_s]
set -uo pipefail
source "$(cd "$(dirname "$0")/../.." && pwd)/tools/macos/rr_env.sh"
cd "$MACVM"
L="$MACVM/mac_launch.log"; MON="$MACVM/mac_mon.sock"; RR="$MACVM/rr/m1"
N="${1:-3}"; WAIT="${2:-150}"
SENT="$MACVM/mac_replay.sentinel"
rm -f "$SENT"; exec > "$MACVM/mac_replay.log" 2>&1
T(){ python3 "$MON_PY" "$MON" "$1" 2>/dev/null; }

echo "=== [$(date)] launch qemu ==="
pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"
screen -dmS mac bash -c "$MACVM/mac_run.sh tcg > $L 2>&1"
for i in $(seq 1 60); do [ -S "$MON" ] && break; sleep 1; done
sleep 3
echo "monitor up after ~${i}s"

for run in $(seq 1 "$N"); do
  echo "############ RUN $run ############"
  PRE=$(grep -acE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" 2>/dev/null); PRE=${PRE:-0}
  T "begin_replay $RR"
  for i in $(seq 1 "$WAIT"); do
    c=$(grep -acE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" 2>/dev/null); c=${c:-0}
    [ "$c" -gt "$PRE" ] && break
    sleep 1
  done
  grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" | tail -1
  T "end_replay" >/dev/null 2>&1
  sleep 1
done
echo "=== [$(date)] DONE ==="
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
