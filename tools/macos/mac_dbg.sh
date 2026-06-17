#!/usr/bin/env bash
# Debug Monterey boot. Usage: mac_dbg.sh <qemu-binary> <kvm|tcg>
# Adds -no-reboot + -d cpu_reset,guest_errors,unimp -D qemu_dbg.log so a guest
# reset / illegal-op / panic is captured instead of silently exiting.
set -u
cd "$HOME/macos"
QEMU="$1"; ACCEL="${2:-tcg}"
OVMF_CODE="OSX-KVM/OVMF_CODE_4M.fd"
OVMF_VARS="mac_vars.fd"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
HDD="monterey_hdd.qcow2"
ISO="macOS_Monterey_12_6_1.iso"
OSK="ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"
cp -f OSX-KVM/OVMF_VARS-1920x1080.fd "$OVMF_VARS"

if [ "$ACCEL" = "kvm" ]; then
  ACCEL_ARGS="-accel kvm"
  CPU="Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt"
else
  ACCEL_ARGS="-accel tcg,thread=single"
  CPU="Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt"
fi

exec "$QEMU" \
  $ACCEL_ARGS -machine q35 -cpu "$CPU" -smp 1 -m 4096 \
  -no-reboot -no-shutdown \
  -d cpu_reset,guest_errors,unimp -D "$HOME/macos/qemu_dbg.log" \
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
  -device vmware-svga -nic none \
  -vnc 127.0.0.1:24 \
  -monitor unix:mac_mon.sock,server,nowait \
  -serial file:mac_serial.log \
  -name monterey-install
