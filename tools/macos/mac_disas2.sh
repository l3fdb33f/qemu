#!/usr/bin/env bash
# Restore the recording's snapshot, run live, and stop until the CPU is in KERNEL
# mode (CPL=0) so kernel text (0xffffff80...) is mapped in the active CR3, then
# disassemble the TSC poll loop.
set -uo pipefail
source "$(cd "$(dirname "$0")/../.." && pwd)/tools/macos/rr_env.sh"
cd "$MACVM"
L="$MACVM/mac_launch.log"; MON="$MACVM/mac_mon.sock"; RR="$MACVM/rr/m1"
SENT="$MACVM/mac_disas.sentinel"
rm -f "$SENT"; exec > "$MACVM/mac_disas.log" 2>&1
T(){ python3 "$MON_PY" "$MON" "$1" 2>/dev/null; }

pkill -9 -f qemu-system-x86_64 2>/dev/null; sleep 2
rm -f "$L" mac_serial.log "$MON"
screen -dmS mac bash -c "$MACVM/mac_run.sh tcg > $L 2>&1"
for i in $(seq 1 60); do [ -S "$MON" ] && break; sleep 1; done
sleep 3
echo "monitor up after ~${i}s"
T "begin_replay $RR" >/dev/null   # restore snapshot (sets the recording KASLR slide)
sleep 2
T "end_replay" >/dev/null         # leave replay -> fully live, timers back
sleep 2

CPL=""; RIP=""
for k in $(seq 1 200); do
  T "stop" >/dev/null
  R=$(T "info registers")
  CPL=$(printf "%s" "$R" | grep -aoE "CPL=[0-9]" | head -1)
  RIP=$(printf "%s" "$R" | grep -aoE "RIP=[0-9a-f]+" | head -1)
  # require real kernel text (ffffff80...), not the KPTI trampoline (fffff6a6...)
  # or userspace (00007f...), so the kernel CR3 is active and kernel text maps.
  if printf "%s" "$RIP" | grep -aqE "RIP=ffffff80"; then
    echo "caught kernel text on try $k: $RIP $CPL"; break
  fi
  T "cont" >/dev/null
  sleep 0.15
done
echo "final: $RIP $CPL"
echo ""
echo "=== CR3 / descriptor regs in kernel mode ==="
T "info registers" | grep -aE "CR3|GDT|IDT"
echo ""
echo "=== disas TSC poll loop 0xffffff801ce1d0e0 (80 insns) ==="
T "x/80i 0xffffff801ce1d0e0"
echo "=== 0xffffff801ce1e080 (40 insns) ==="
T "x/40i 0xffffff801ce1e080"
pkill -9 -f qemu-system-x86_64 2>/dev/null
echo done > "$SENT"
