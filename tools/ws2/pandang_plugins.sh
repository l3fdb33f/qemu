#!/usr/bin/env bash
# WS-2 step 3: build the Linux introspection plugins (osi/osi_linux/syscalls2)
# against the natively-generated panda-ng headers.
set -uo pipefail

LOG=~/pandang_plugins.log
SENT=~/pandang_plugins.sentinel
rm -f "$SENT"
exec > "$LOG" 2>&1

PLUGREPO=~/panda-ng

echo "=== [$(date)] install meson + pycparser (pip --user) ==="
python3 -m pip install --user --break-system-packages meson pycparser 2>&1 | tail -3
export PATH="$HOME/.local/bin:$PATH"
meson --version || { echo "MESON_MISSING"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] install rust/cargo (rustup, minimal) ==="
if ! command -v cargo >/dev/null 2>&1; then
    curl https://sh.rustup.rs -sSf | sh -s -- -y --profile minimal 2>&1 | tail -3
fi
export PATH="$HOME/.cargo/bin:$PATH"
cargo --version || { echo "CARGO_MISSING"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] provision headers into local_packages/panda-ng ==="
mkdir -p "$PLUGREPO/local_packages/panda-ng"
cp -v ~/libpanda-ng/build/panda_c_x86_64.h \
      ~/libpanda-ng/build/panda_cpp_x86_64.h \
      ~/libpanda-ng/build/panda_python_x86_64.h \
      "$PLUGREPO/local_packages/panda-ng/"

echo "=== [$(date)] trim config.panda to Linux introspection stack ==="
# hw_proc_id: ext header needed by syscalls2 + osi_linux + hooks.
# hooks: panda_require'd by syscalls2 at runtime.
cat > "$PLUGREPO/plugins/config.panda" <<'EOF'
hw_proc_id
hooks
osi
osi_linux
proc_start_linux
syscalls2
EOF
cat "$PLUGREPO/plugins/config.panda"

echo "=== [$(date)] meson setup (x86_64-softmmu only) ==="
cd "$PLUGREPO"
rm -rf build
meson setup build -Dtargets='["x86_64-softmmu"]' 2>&1 | tail -30 \
    || { echo "MESON_SETUP_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] ninja ==="
cd "$PLUGREPO/build"
ninja 2>&1 | tail -40 || { echo "NINJA_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] pandare2 python bindings (cffi autogen) ==="
# Reads local_packages/panda-ng/panda_python_x86_64.h, emits the ABI-mode
# _pandare_ffi_x86_64_softmmu.py so `import pandare2` + Panda() works.
cd "$PLUGREPO/python/core"
python3 setup.py build_python_autogen 2>&1 | tail -5 \
    || { echo "AUTOGEN_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] DONE ==="
echo "--- built plugin .so files ---"
find "$PLUGREPO/build/plugins" -maxdepth 1 -name "libpanda-*.so" | sort
echo OK > "$SENT"
