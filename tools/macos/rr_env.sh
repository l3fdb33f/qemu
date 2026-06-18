#!/usr/bin/env bash
# Shared environment for panda-ng RR / introspection harnesses. `source` this.
#
# Paths are DERIVED, not hardcoded, so the harnesses keep working no matter
# where the repos live (rename-proof):
#   * PANDA_QEMU   = the qemu-core repo (l3fdb33f/qemu). Auto-detected from this
#                    file location (tools/macos/rr_env.sh -> repo root).
#   * PANDA_PLUGINS= the plugins repo (l3fdb33f/panda-ng). Defaults to a sibling
#                    dir; override via the environment if elsewhere.
# Override any variable by exporting it before sourcing.
_RR_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${PANDA_QEMU:=$(cd "$_RR_ENV_DIR/../.." && pwd)}"
: "${PANDA_PLUGINS:=$HOME/panda-ng}"
: "${MACVM:=$HOME/macos}"
: "${WINVM:=$HOME/winrr}"

QEMU_BIN="$PANDA_QEMU/build/qemu-system-x86_64"
LIBPANDA="$PANDA_QEMU/build/libpanda-x86_64-softmmu.so"
PCBIOS="$PANDA_QEMU/pc-bios"
MON_PY="$PANDA_QEMU/tools/macos/mon.py"
PLUGINS_DIR="$PANDA_PLUGINS/build/plugins"
PANDARE2="$PANDA_PLUGINS/python/core"
export PANDA_QEMU PANDA_PLUGINS MACVM WINVM QEMU_BIN LIBPANDA PCBIOS MON_PY PLUGINS_DIR PANDARE2
