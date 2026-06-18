#!/usr/bin/env bash
# Monterey install on jack (x86_64 AMD host). KVM-accelerated by default.
#   ./mac_install.sh [kvm|tcg]
# Boots OpenCore (AMD-patched) + the Monterey installer ISO + the target disk.
# Drive via VNC :24 (vncdotool); steer OpenCore picker via monitor mac_mon.sock.
set -u
cd "$HOME/macos"
ACCEL="${1:-kvm}"
QEMU="${QEMU_BIN:-$HOME/qemu/build/qemu-system-x86_64}"
OVMF_CODE="OSX-KVM/OVMF_CODE_4M.fd"
OVMF_VARS_SRC="OSX-KVM/OVMF_VARS-1920x1080.fd"
OVMF_VARS="mac_vars.fd"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
HDD="monterey_hdd.qcow2"
ISO="macOS_Monterey_12_6_1.iso"
OSK="ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"
[ -f "$OVMF_VARS" ] || cp "$OVMF_VARS_SRC" "$OVMF_VARS"

if [ "$ACCEL" = "kvm" ]; then
  ACCEL_ARGS="-accel kvm"
  CPU="Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+ssse3,+sse4.1,+sse4.2,+popcnt,+aes,+pclmulqdq,+xsave,+xsaveopt"
else
  ACCEL_ARGS="-accel tcg,thread=single"
  CPU="Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+aes,+pclmulqdq,+xsave,+xsaveopt"
fi

exec "$QEMU" \
  $ACCEL_ARGS \
  -machine q35 \
  -cpu "$CPU" \
  -smp 1 -m 4096 \
  -device isa-applesmc,osk="$OSK" \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,file="$OVMF_VARS" \
  -smbios type=2 \
  -device ich9-ahci,id=sata \
  -drive id=OpenCoreBoot,if=none,format=qcow2,file="$OC" \
  -device ide-hd,bus=sata.0,drive=OpenCoreBoot \
  -drive id=MacHDD,if=none,format=qcow2,file="$HDD" \
  -device ide-hd,bus=sata.1,drive=MacHDD \
  -drive id=InstallMedia,if=none,format=raw,media=cdrom,file="$ISO" \
  -device ide-cd,bus=sata.2,drive=InstallMedia \
  -global ICH9-LPC.disable_s3=1 -global ICH9-LPC.disable_s4=1 \
  -usb -device qemu-xhci,id=xhci -device usb-kbd -device usb-tablet \
  -device vmware-svga \
  -nic none \
  -vnc 127.0.0.1:24 \
  -monitor unix:mac_mon.sock,server,nowait \
  -serial file:mac_serial.log \
  -name monterey-install
