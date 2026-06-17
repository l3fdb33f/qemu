# panda-ng tools (WS-2 build & introspection)

Native x86_64 build + introspection tooling for panda-ng on this host.
Repos involved (all cloned in `$HOME`, NOT under `~/panda` or `~/pandbox`):
- `~/panda-ng`           — core (l3fdb33f/qemu, branch wip/record-replay)
- `~/libpanda-ng`        — gdb-DWARF header generator (panda-re/libpanda-ng)
- `~/panda-ng-plugins`   — plugins (l3fdb33f/panda-ng)

## Build pipeline (run in order)
1. `pandang_bootstrap.sh`  — clone core + configure + ninja (x86_64-softmmu).
                             Produces libpanda-x86_64-softmmu.so + qemu-system-x86_64.
2. `pandang_headers.sh`    — clone libpanda-ng, run_all.sh → panda_c/cpp/python_x86_64.h
3. `pandang_plugins.sh`    — install meson+cargo, provision headers into
                             panda-ng-plugins/local_packages/panda-ng, build the
                             Linux introspection plugins (osi/osi_linux/proc_start_linux/
                             syscalls2 + hw_proc_id) for x86_64-softmmu only.

Each writes ~/<name>.log and ~/<name>.sentinel (OK/FAIL or exit code).

## Verification
- `abi_check.sh`     — confirm every panda_*/ppp_* symbol each plugin needs is
                       exported by libpanda (ABI correctness of the port).
- `import_test.py`   — import pandare2 against the local build + construct a Panda
                       (no boot). Requires the pandare2 autogen step first:
                       `cd ~/panda-ng-plugins/python/core && python3 setup.py build_python_autogen`
- `live_syscalls.py` — boot alpine-virt.iso under panda-ng, load syscalls2, count
                       on_all_sys_enter callbacks. End-to-end introspection proof.
                       VERIFIED: 20,015 syscall-enter callbacks captured from a live
                       Alpine boot; correctly decoded x86_64 Linux numbers
                       (fcntl/open/close/read/mmap/...). PROOF_OK.

## Notes
- pandare2 needs an OS profile for syscalls2: os_version="linux-64-alpine".
- osi_linux additionally needs a guest kernel profile (kernelinfo) to walk task
  structs — not yet provisioned (next sub-task; shares shape with the Monterey
  XNU ISF work).
- Two upstream fixes were required and live in the repos (not here):
  * panda-ng-plugins/plugins/meson.build — guard for plugins whose main source
    isn't named <plugin>.c (osi's is os_intro.c).
  * panda-ng-plugins/python/core/pandare_build.py — inject stdint typedefs before
    cffi.cdef (newer cffi/pycparser no longer pre-register uint64_t etc.).
