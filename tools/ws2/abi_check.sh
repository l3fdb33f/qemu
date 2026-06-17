#!/usr/bin/env bash
# ABI verification: for each ported plugin, confirm every UND (undefined) symbol
# is satisfied by libpanda or the standard runtime libs it will be loaded with.
set -uo pipefail
LIBPANDA=~/panda-ng/build/libpanda-x86_64-softmmu.so
PLUGDIR=~/panda-ng-plugins/build/plugins
IFACE=~/panda-ng/build/contrib/plugins/libpanda_plugin_interface.so

# Symbols exported (defined, T/W/etc — not U) by libpanda + the interface + the
# system libs the process will have loaded (libc, libstdc++, glib, gmodule, curl).
provided=$(mktemp)
{
  nm -D --defined-only "$LIBPANDA" 2>/dev/null | awk '{print $NF}'
  nm -D --defined-only "$IFACE" 2>/dev/null | awk '{print $NF}'
  for L in /usr/lib/x86_64-linux-gnu/libc.so.6 \
           /usr/lib/x86_64-linux-gnu/libstdc++.so.6 \
           /usr/lib/x86_64-linux-gnu/libm.so.6 \
           /usr/lib/x86_64-linux-gnu/libgcc_s.so.1 \
           /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0 \
           /usr/lib/x86_64-linux-gnu/libgmodule-2.0.so.0 \
           $(ls /usr/lib/x86_64-linux-gnu/libcurl.so* 2>/dev/null | head -1); do
    [ -e "$L" ] && nm -D --defined-only "$L" 2>/dev/null | awk '{print $NF}'
  done
} | sort -u > "$provided"

echo "provided-symbol universe: $(wc -l < "$provided") symbols"
echo

rc=0
for so in "$PLUGDIR"/libpanda-*_x86_64-softmmu.so; do
  name=$(basename "$so")
  # undefined symbols the plugin needs (strip the trailing version tags)
  und=$(nm -D --undefined-only "$so" 2>/dev/null | awk '{print $NF}' | sed 's/@.*//' | sort -u)
  missing=$(comm -23 <(echo "$und") "$provided")
  # ignore the ifunc/standard glibc weak resolvers that are always satisfied
  missing=$(echo "$missing" | grep -vE '^(__|_ITM_|_Unwind_|$)' || true)
  nmiss=$(echo "$missing" | grep -c . || true)
  if [ "$nmiss" -eq 0 ]; then
    echo "OK   $name  (all $(echo "$und" | grep -c .) UND symbols resolved)"
  else
    echo "MISS $name  -> $nmiss unresolved:"
    echo "$missing" | sed 's/^/        /'
    rc=1
  fi
done
echo
echo "exit=$rc"
