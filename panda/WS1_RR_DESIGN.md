# WS-1: Device-agnostic Record/Replay on panda-ng (QEMU 10.2.50)

Goal: port classic PANDA's **device-agnostic** RR (records nondeterminism crossing the
CPU/RAM boundary; replays without re-running devices) onto panda-ng. De-risk on Alpine
Linux, then Monterey. QEMU-native icount-rr is per-device → unusable for macOS; this is
the classic PANDA model.

## Core model (unchanged from classic)
- **prog_point = a 64-bit guest-instruction counter** (`rr_guest_instr_count`). It is the ONLY
  clock; every log entry is tagged with it. Not QEMU icount — our own monotonic counter.
- **Record:** snapshot full machine (save_snapshot) at begin; then log every nondeterministic
  input tagged with the current instr-count: IO/MMIO reads (RR_INPUT_*), interrupt_request
  changes, injected interrupt vector, RDTSC, and device→RAM DMA / unmap write-back
  (RR_SKIPPED_CALL). RAM reads are deterministic → NOT logged (gate on !memory_region_is_ram).
- **Replay:** load_snapshot; re-execute single-thread TCG; at each capture point, instead of
  touching the device, pop the next log entry — which MUST match the current instr-count — and
  return its recorded value. Devices are NOT polled in replay (their effects are replayed from
  the skipped-call log). Determinism substrate = `-accel tcg,thread=single`.

## panda-ng re-homing table (verified file:line)
| Classic 2.9.1 | panda-ng (QEMU 10.2.50) | hook |
|---|---|---|
| address_space_read RR_INPUT | system/physmem.c flatview_read 3381 / flatview_read_continue_step memory_region_dispatch_read 3322 | record IO-region read value+MemTxResult |
| cpu_physical_memory_rw (DMA) | system/physmem.c flatview_write 3290 / address_space_write 3412 | record dev→RAM write as RR_CALL_CPU_MEM_RW |
| address_space_unmap write-back | system/physmem.c address_space_unmap 3751 (bounce write-back ~3767) | RR_CALL_CPU_MEM_UNMAP |
| cpu-exec interrupt | accel/tcg/cpu-exec.c cpu_handle_interrupt 818 (reads interrupt_request ~859, calls tcg_ops->cpu_exec_interrupt ~880) | record/replay interrupt_request |
| intno read | target/i386/tcg/system/seg_helper.c x86_cpu_exec_interrupt 165 | record/replay injected vector |
| helper_rdtsc | target/i386/tcg/misc_helper.c helper_rdtsc 71 | record/replay TSC (RR_INPUT_8) |
| gen_op_update_rr_icount | accel/tcg/translator.c translator_loop while-loop (after insn_start, ~line 160) | emit per-insn increment of cpu->rr_guest_instr_count |
| CPUState.rr_guest_instr_count | include/hw/core/cpu.h CPUState (add field before neg_align @595) | the prog_point clock |
| qemu_savevm_state | migration/savevm.c save_snapshot 3189 / load_snapshot 3382 | record-begin snapshot / replay restore |
| main_loop_wait hooks | util/main-loop.c main_loop_wait 563 | rr_begin/end_main_loop_wait around device poll |
| begin_record/replay monitor | hmp-commands.hx + qapi/ + new handlers | RR control |
| cpu_exec loop | accel/tcg/cpu-exec.c cpu_exec 1062 / cpu_exec_setjmp 1052 | mode transition + count sanity check |

## Log format (ported verbatim from classic rr_log_all.h)
- RR_log_entry_kind: RR_INPUT_1/2/4/8, RR_INTERRUPT_REQUEST, RR_EXIT_REQUEST, RR_SKIPPED_CALL,
  RR_END_OF_LOG, RR_PENDING_INTERRUPTS, RR_EXCEPTION, RR_LAST.
- RR_skipped_call_kind: RR_CALL_CPU_MEM_RW, RR_CALL_MEM_REGION_CHANGE, RR_CALL_CPU_MEM_UNMAP,
  RR_CALL_HD_TRANSFER, RR_CALL_NET_TRANSFER, ... RR_CALL_LAST.
- RR_header{ prog_point(u64 instr_count), file_pos, kind, callsite_loc }; RR_log_entry{ header, union variant }.
- On-disk: instr_count(8) | kind(1) | callsite(1) | variant.

## Incremental build/test plan (de-risk on Alpine first)
- **1a (FOUNDATION, this increment): the instruction-count clock.** Add CPUState.rr_guest_instr_count;
  emit per-insn TCG increment in translator_loop gated by a global `rr_mode != OFF`; tb_flush on
  mode toggle so all TBs carry (or drop) the increment. Add `info rr` HMP to print mode+count.
  VERIFY: boot Alpine, `info rr` shows a large advancing count. Exit: clock compiles + advances.
- **1b: nondet log + mode control + monitor cmds.** rr_log.[ch], rr_types.h, rr_api.h: RR_log/entry
  structs, open/close nondet log, write/read entry, the replay queue (rr_fill_queue/pop), rr_control
  state machine, begin_record/end_record/begin_replay/end_replay HMP+QMP wired to save_snapshot/
  load_snapshot. No capture points yet (empty log). VERIFY: begin_record→run→end_record produces a
  snapshot file + (empty) nondet log; begin_replay loads snapshot.
- **2: capture points (record).** RR_INPUT (physmem.c IO reads), RDTSC, interrupt_request + intno,
  DMA writes (flatview_write) + unmap. main_loop_wait guards. VERIFY: record Alpine boot segment;
  log grows with entries of each kind; counts sane.
- **3: replay driver.** Pop-and-return at each capture point with instr-count assertion; skipped-call
  replay for DMA; interrupt replay. VERIFY (THE milestone): record a bounded Alpine workload, replay
  it, confirm replay reaches the SAME final rr_guest_instr_count and identical RAM hash → determinism.
- **4: harden + Monterey.** Edge cases (mem region change, bounce buffers, xhci/ahci DMA volume),
  RR2 archive packaging, then validate record/replay on Monterey.

## Risks
- Modern TCG block-chaining / can_do_io: per-insn increment must survive TB chaining and exact at
  capture points (classic forced TB exit on interrupt; verify exitreq path). 
- save/load_snapshot needs a block backend that supports internal snapshots (qcow2) OR file-based
  vmstate; Alpine ISO is read-only → use a scratch qcow2 overlay or `-blockdev` vmstate file.
- determinism validation must gate on identical device set + no wall-clock leakage beyond RDTSC.
