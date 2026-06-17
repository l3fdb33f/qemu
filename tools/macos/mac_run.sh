#!/usr/bin/env bash
# Boot the INSTALLED Monterey disk under panda-ng (our RR core) on jack.
# No ISO. Run under screen. Default qemu = panda-ng build.
#   ./mac_run.sh [tcg|kvm]
set -u
cd "$HOME/macos"
ACCEL="${1:-tcg}"
QEMU="${QEMU_BIN:-$HOME/panda-ng/build/qemu-system-x86_64}"
OVMF_CODE="OSX-KVM/OVMF_CODE_4M.fd"
OVMF_VARS="mac_vars.fd"
OC="OSX-KVM/OpenCore/OpenCore.qcow2"
HDD="monterey_hdd.qcow2"
OSK="ourhardworkbythesewordsguardedpleasedontsteal(c)AppleComputerInc"
[ -f "$OVMF_VARS" ] || cp OSX-KVM/OVMF_VARS-1920x1080.fd "$OVMF_VARS"

if [ "$ACCEL" = "kvm" ]; then
  ACCEL_ARGS="-accel kvm"
  CPU="Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt"
else
  ACCEL_ARGS="-accel tcg,thread=single"
  CPU="Penryn,vendor=GenuineIntel,+ssse3,+sse4.1,+sse4.2,+popcnt,+avx,+aes,+pclmulqdq,+xsave,+xsaveopt"
fi

exec "$QEMU" \
  $ACCEL_ARGS -machine q35 -cpu "$CPU" -smp 1 -m 4096 \
  -device isa-applesmc,osk="$OSK" \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,file="$OVMF_VARS" \
  -smbios type=2 \
  -device ich9-ahci,id=sata \
  -drive id=OpenCoreBoot,if=none,format=qcow2,file="$OC" \
  -device ide-hd,bus=sata.0,drive=OpenCoreBoot \
  -drive id=MacHDD,if=none,format=qcow2,file="$HDD" \
  -device ide-hd,bus=sata.1,drive=MacHDD \
  -global ICH9-LPC.disable_s3=1 -global ICH9-LPC.disable_s4=1 \
  -usb -device qemu-xhci,id=xhci -device usb-kbd -device usb-tablet \
  -device vmware-svga -nic none \
  -vnc 127.0.0.1:24 \
  -monitor unix:mac_mon.sock,server,nowait \
  -serial file:mac_serial.log \
  -name monterey-install
