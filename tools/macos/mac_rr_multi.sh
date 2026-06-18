#!/usr/bin/env bash
# Multi-segment bounded RR from a SINGLE boot (boot is the expensive part).
#   mac_rr_multi.sh "cap1 cap2 cap3 ..." [replay_wait_s]
# Boots Monterey once, then for each cap: begin_record (auto-stop) -> begin_replay
# -> record outcome. Guest runs live between cycles, so successive segments cover
# progressively-advanced guest states. Output -> ~/macos/mac_rr.log.
set -uo pipefail
source "$(cd "$(dirname "$0")/../.." && pwd)/tools/macos/rr_env.sh"
cd "$MACVM"
L="$MACVM/mac_launch.log"; MON="$MACVM/mac_mon.sock"
CAPS="${1:-20000000 100000000 300000000}"; WAIT="${2:-900}"
SENT="$MACVM/mac_rr.sentinel"
rm -f "$SENT"; exec > "$MACVM/mac_rr.log" 2>&1
T(){ python3 "$MON_PY" "$MON" "$1" 2>/dev/null; }
rrcount(){ T "info rr" | grep -a rr_guest | grep -oE '[0-9]+' | tail -1; }
# Count matching lines in the launch log as a clean single integer (grep -c
# already prints 0 on no-match; never append "|| echo 0" -- that yields "0\n0").
cnt(){ local c; c=$(grep -acE "$1" "$L" 2>/dev/null); echo "${c:-0}"; }

echo "=== [$(date)] launch qemu under screen ==="
pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"; rm -rf "$MACVM/rr"; mkdir -p "$MACVM/rr"
screen -dmS mac bash -c "$MACVM/mac_run.sh tcg > $L 2>&1"

echo "=== wait for boot ==="
for i in $(seq 1 400); do
  grep -qa "IOConsoleUsers\|gIOScreenLockState" mac_serial.log 2>/dev/null && break
  sleep 1
done
echo "booted after ~${i}s; free-running rr clock: $(rrcount)"
sleep 5

n=0
for CAP in $CAPS; do
  n=$((n+1)); RR="$MACVM/rr/seg$n"
  echo ""
  echo "############################################################"
  echo "### [$(date)] SEGMENT $n  cap=$CAP"
  echo "############################################################"
  MARK="bounded record complete"
  PRE=$(cnt "$MARK")
  T "begin_record $RR $CAP"
  for i in $(seq 1 240); do
    [ "$(cnt "$MARK")" -gt "$PRE" ] && break
    sleep 0.5
  done
  grep -a "$MARK" "$L" | tail -1
  echo "nondet: $(stat -c%s "$RR-rr-nondet.log" 2>/dev/null) bytes; snap: $(stat -c%s "$RR-rr-snp" 2>/dev/null) bytes"

  OUT="RR DIVERGENCE|RR REPLAY COMPLETE"
  PRE2=$(cnt "$OUT")
  RSTART=$(date +%s)
  T "begin_replay $RR"
  for i in $(seq 1 "$WAIT"); do
    [ "$(cnt "$OUT")" -gt "$PRE2" ] && break
    sleep 1
  done
  RELAPSED=$(( $(date +%s) - RSTART ))
  echo "--- SEG $n OUTCOME (replay waited ${i}s / wall ${RELAPSED}s) ---"
  grep -aE "RR DIVERGENCE|RR REPLAY COMPLETE" "$L" | tail -1 || echo "<none / still running>"
  # leave replay mode if it diverged (rr_mode stays REPLAY on divergence)
  T "end_replay" >/dev/null 2>&1
  rm -f "$RR-rr-snp"   # reclaim ~1.5GB; keep the tiny nondet log for analysis
  sleep 2
done

echo ""
echo "=== [$(date)] ALL SEGMENTS DONE ==="
grep -aE "bounded record complete|RR DIVERGENCE|RR REPLAY COMPLETE" "$L"
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
