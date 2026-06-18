/*
 * PANDA-NG record/replay core (WS-1).
 * Increment 1b: mode state machine + device-agnostic snapshot + nondet log
 * open/close + HMP control plane. Capture points (Inc 2) and the replay
 * driver/queue (Inc 3) are added in later increments.
 */
#include "qemu/osdep.h"
#include "qemu/cutils.h"
#include "qemu/error-report.h"
#include "qapi/error.h"
#include "qobject/qdict.h"
#include "monitor/monitor.h"
#include "monitor/hmp.h"
#include "hw/core/cpu.h"
#include "exec/cpu-common.h"
#include "system/runstate.h"
#include "migration/snapshot.h"
#include "rr_log.h"

volatile RR_mode rr_mode = RR_OFF;

static FILE *rr_nondet_log;
static char  rr_name[1024];

uint64_t rr_get_guest_instr_count(void)
{
    return first_cpu ? first_cpu->rr_guest_instr_count : 0;
}

RR_mode rr_get_mode(void) { return rr_mode; }

static void rr_reset_count(void)
{
    CPUState *cpu;
    CPU_FOREACH(cpu) {
        cpu->rr_guest_instr_count = 0;
    }
}

/* On-disk entry layout: instr_count(u64) | kind(u8) | callsite(u8) | [variant]. */
static void rr_write_entry_header(RR_log_entry_kind kind)
{
    uint64_t ic = rr_get_guest_instr_count();
    uint8_t k = (uint8_t)kind;
    uint8_t cs = 0;
    flockfile(rr_nondet_log);
    fwrite(&ic, sizeof(ic), 1, rr_nondet_log);
    fwrite(&k,  sizeof(k),  1, rr_nondet_log);
    fwrite(&cs, sizeof(cs), 1, rr_nondet_log);
    funlockfile(rr_nondet_log);
}


/* ----------------------------- RECORD writers ----------------------------- */
/* On-disk variant payloads follow the (instr_count, kind, callsite) header. */
static void rr_log_write(RR_log_entry_kind kind, const void *data, size_t n)
{
    uint64_t ic;
    uint8_t k, cs = 0;

    if (!rr_nondet_log) {
        return;
    }
    ic = rr_get_guest_instr_count();
    k = (uint8_t)kind;
    /* Whole entry under the FILE lock: device-DMA capture can run on a different
     * context than the vCPU capture; per-field fwrites would otherwise interleave
     * and corrupt the log. */
    flockfile(rr_nondet_log);
    fwrite(&ic, sizeof(ic), 1, rr_nondet_log);
    fwrite(&k,  sizeof(k),  1, rr_nondet_log);
    fwrite(&cs, sizeof(cs), 1, rr_nondet_log);
    if (n) {
        fwrite(data, n, 1, rr_nondet_log);
    }
    funlockfile(rr_nondet_log);
}

void rr_record_input_1(uint8_t v)  { rr_log_write(RR_INPUT_1, &v, sizeof(v)); }
void rr_record_input_2(uint16_t v) { rr_log_write(RR_INPUT_2, &v, sizeof(v)); }
void rr_record_input_4(uint32_t v) { rr_log_write(RR_INPUT_4, &v, sizeof(v)); }
void rr_record_input_8(uint64_t v) { rr_log_write(RR_INPUT_8, &v, sizeof(v)); }

void rr_record_io_read(uint64_t val, unsigned size)
{
    switch (size) {
    case 1:  rr_record_input_1((uint8_t)val);  break;
    case 2:  rr_record_input_2((uint16_t)val); break;
    case 4:  rr_record_input_4((uint32_t)val); break;
    default: rr_record_input_8(val);           break;
    }
}

void rr_record_interrupt_request(int interrupt_request)
{
    int32_t v = interrupt_request;
    rr_log_write(RR_INTERRUPT_REQUEST, &v, sizeof(v));
}

void rr_record_exception_index(int exception_index)
{
    int32_t v = exception_index;
    rr_log_write(RR_EXCEPTION, &v, sizeof(v));
}

/* ----------------------------- REPLAY (Inc 3a) ---------------------------- */
/* In-memory copy of the nondet log, consumed in order during replay. Pull
 * events (RDTSC, IO reads) must match the recorded kind AND prog point exactly;
 * a mismatch is a divergence (the replay oracle). Interrupt injection lands in
 * Increment 3b. */
typedef struct {
    uint64_t count;   /* prog point = guest instruction count */
    uint8_t  kind;
    uint8_t  cs;
    uint64_t val;     /* variant payload, zero-extended */
    uint64_t dma_addr;  /* RR_SKIPPED_CALL: device->RAM DMA guest phys addr */
    uint32_t dma_len;
    uint8_t *dma_buf;
} RR_entry;

static RR_entry *rr_entries;
static size_t    rr_nentries;
static size_t    rr_idx;
static uint64_t  rr_final_count;
static uint64_t  rr_record_until;   /* bounded record cap (0 = unbounded) */
static int       rr_record_done;    /* set once a bounded record auto-finalized */
static int       rr_diverged;
static int       rr_div_reported;
static uint64_t  rr_replayed_pulls;
static uint64_t *rr_next_int_count;

static size_t rr_variant_size(uint8_t kind)
{
    switch (kind) {
    case RR_INPUT_1: return 1;
    case RR_INPUT_2: return 2;
    case RR_INPUT_4: return 4;
    case RR_INPUT_8: return 8;
    case RR_INTERRUPT_REQUEST: return 4;
    case RR_EXCEPTION: return 4;
    default: return 0; /* RR_END_OF_LOG etc. */
    }
}

/* Read the remaining nondet log (positioned past the 8-byte header) into RAM. */
static int rr_replay_load_entries(void)
{
    size_t cap = 4096;
    rr_entries = g_new(RR_entry, cap);
    rr_nentries = 0;
    for (;;) {
        uint64_t ic;
        uint8_t kind, cs;
        uint64_t val = 0;
        size_t vs;
        if (fread(&ic, sizeof(ic), 1, rr_nondet_log) != 1) {
            break;
        }
        if (fread(&kind, 1, 1, rr_nondet_log) != 1) {
            break;
        }
        if (fread(&cs, 1, 1, rr_nondet_log) != 1) {
            break;
        }
        uint64_t dma_addr = 0;
        uint32_t dma_len = 0;
        uint8_t *dma_buf = NULL;
        if (kind == RR_SKIPPED_CALL) {
            if (fread(&dma_addr, sizeof(dma_addr), 1, rr_nondet_log) != 1) {
                break;
            }
            if (fread(&dma_len, sizeof(dma_len), 1, rr_nondet_log) != 1) {
                break;
            }
            if (dma_len) {
                dma_buf = g_malloc(dma_len);
                if (fread(dma_buf, dma_len, 1, rr_nondet_log) != 1) {
                    g_free(dma_buf);
                    break;
                }
            }
        } else {
            vs = rr_variant_size(kind);
            if (vs && fread(&val, vs, 1, rr_nondet_log) != 1) {
                break;
            }
        }
        if (rr_nentries == cap) {
            cap *= 2;
            rr_entries = g_renew(RR_entry, rr_entries, cap);
        }
        rr_entries[rr_nentries].count = ic;
        rr_entries[rr_nentries].kind = kind;
        rr_entries[rr_nentries].cs = cs;
        rr_entries[rr_nentries].val = val;
        rr_entries[rr_nentries].dma_addr = dma_addr;
        rr_entries[rr_nentries].dma_len = dma_len;
        rr_entries[rr_nentries].dma_buf = dma_buf;
        rr_nentries++;
        if (kind == RR_END_OF_LOG) {
            break;
        }
    }
    rr_next_int_count = g_new(uint64_t, rr_nentries ? rr_nentries : 1);
    {
        uint64_t nxt = rr_final_count;
        ssize_t i;
        for (i = (ssize_t)rr_nentries - 1; i >= 0; i--) {
            if (rr_entries[i].kind == RR_INTERRUPT_REQUEST ||
                rr_entries[i].kind == RR_SKIPPED_CALL ||
                rr_entries[i].kind == RR_END_OF_LOG) {
                nxt = rr_entries[i].count;
            }
            rr_next_int_count[i] = nxt;
        }
    }
    rr_idx = 0;
    rr_diverged = 0;
    rr_div_reported = 0;
    rr_replayed_pulls = 0;
    info_report("RR: loaded %zu nondet log entries (final count %llu)",
                rr_nentries, (unsigned long long)rr_final_count);
    return rr_nentries > 0 ? 0 : -1;
}

static void rr_report_divergence(const char *what, uint8_t want_kind)
{
    uint64_t cur = rr_get_guest_instr_count();
    if (rr_div_reported) {
        return;
    }
    rr_div_reported = 1;
    rr_diverged = 1;
    if (rr_idx < rr_nentries) {
        RR_entry *e = &rr_entries[rr_idx];
        error_report("RR DIVERGENCE: %s; cur_instr=%llu want_kind=%u; "
                     "next log entry idx=%zu kind=%u count=%llu; replayed_pulls=%llu",
                     what, (unsigned long long)cur, want_kind, rr_idx, e->kind,
                     (unsigned long long)e->count,
                     (unsigned long long)rr_replayed_pulls);
    } else {
        error_report("RR DIVERGENCE: %s; cur_instr=%llu want_kind=%u; "
                     "log EXHAUSTED; replayed_pulls=%llu",
                     what, (unsigned long long)cur, want_kind,
                     (unsigned long long)rr_replayed_pulls);
    }
}

static int rr_replay_pull(uint8_t kind, uint64_t *out)
{
    uint64_t cur;
    RR_entry *e;
    if (rr_diverged) {
        return -1;
    }
    cur = rr_get_guest_instr_count();
    /* Same-count SKIPPED_CALL/input ordering. A device DMA (SKIPPED_CALL) and a
     * CPU input read can share an instruction count, with the SKIP recorded
     * first. The DMA can only be applied at a loop-top (a mid-TB RAM write can
     * invalidate the running TB), but its order vs a same-count input is
     * immaterial -- the DMA lands at the same count either way. If a run of
     * same-count SKIPs blocks the matching input, rotate the input ahead of them
     * so the pull consumes it now; the SKIPs still apply at the next loop-top
     * (apply_dma drains count<=cur). */
    if (rr_idx < rr_nentries && rr_entries[rr_idx].kind == RR_SKIPPED_CALL) {
        size_t j = rr_idx;
        while (j < rr_nentries && rr_entries[j].kind == RR_SKIPPED_CALL &&
               rr_entries[j].count <= cur) {
            j++;
        }
        if (j < rr_nentries && rr_entries[j].kind == kind &&
            rr_entries[j].count == cur) {
            RR_entry input = rr_entries[j];
            size_t k;
            for (k = j; k > rr_idx; k--) {
                rr_entries[k] = rr_entries[k - 1];
            }
            rr_entries[rr_idx] = input;
            /* Keep the parallel next-interrupt-count array consistent: all the
             * rotated entries [rr_idx..j] are at the same count (cur), and each
             * is now followed by a same-count SKIP boundary (or is one), so the
             * next boundary for every one of them is cur. */
            if (rr_next_int_count) {
                for (k = rr_idx; k <= j; k++) {
                    rr_next_int_count[k] = cur;
                }
            }
        }
    }
    if (rr_idx >= rr_nentries) {
        rr_report_divergence("log exhausted on pull", kind);
        return -1;
    }
    e = &rr_entries[rr_idx];
    if (e->kind != kind || e->count != cur) {
        rr_report_divergence("pull kind/count mismatch", kind);
        return -1;
    }
    *out = e->val;
    rr_idx++;
    rr_replayed_pulls++;
    return 0;
}

void rr_replay_input_1(uint8_t *val)  { uint64_t v; if (rr_replay_pull(RR_INPUT_1, &v) == 0) { *val = (uint8_t)v; } }
void rr_replay_input_2(uint16_t *val) { uint64_t v; if (rr_replay_pull(RR_INPUT_2, &v) == 0) { *val = (uint16_t)v; } }
void rr_replay_input_4(uint32_t *val) { uint64_t v; if (rr_replay_pull(RR_INPUT_4, &v) == 0) { *val = (uint32_t)v; } }
void rr_replay_input_8(uint64_t *val) { uint64_t v; if (rr_replay_pull(RR_INPUT_8, &v) == 0) { *val = v; } }

void rr_replay_io_read(uint64_t *val, unsigned size)
{
    switch (size) {
    case 1: { uint8_t  v = (uint8_t)*val;  rr_replay_input_1(&v); *val = v; break; }
    case 2: { uint16_t v = (uint16_t)*val; rr_replay_input_2(&v); *val = v; break; }
    case 4: { uint32_t v = (uint32_t)*val; rr_replay_input_4(&v); *val = v; break; }
    default:{ uint64_t v = *val;           rr_replay_input_8(&v); *val = v; break; }
    }
}

int rr_replay_diverged(void) { return rr_diverged; }

int rr_replay_finished(void)
{
    return rr_get_guest_instr_count() >= rr_final_count;
}


/* Write END_OF_LOG, backpatch the final guest instruction count into the
 * reserved 8-byte header, close the nondet log, and leave RR. Shared by the
 * HMP end_record path and the bounded auto-finalize. Callers must guarantee no
 * concurrent capture (HMP path quiesces via vm_stop; bounded path runs on the
 * vCPU thread between TBs, where capture hooks cannot be mid-write). */
static void rr_finish_record_log(void)
{
    uint64_t final_count = rr_get_guest_instr_count();
    rr_write_entry_header(RR_END_OF_LOG);
    if (fseek(rr_nondet_log, 0, SEEK_SET) == 0) {
        fwrite(&final_count, sizeof(final_count), 1, rr_nondet_log);
    }
    fclose(rr_nondet_log);
    rr_nondet_log = NULL;
    rr_mode = RR_OFF;
}

void rr_record_set_until(uint64_t count) { rr_record_until = count; }
uint64_t rr_record_get_until(void)       { return rr_record_until; }
int rr_record_bounded_done(void)         { return rr_record_done; }

/* Per-TB hook (cpu-exec loop): when a cap is armed, auto-finalize the recording
 * the moment the guest instruction count crosses it. Granularity is one TB
 * (we may finalize a few instrs past the cap) which is fine for a debug bound. */
void rr_record_check_bound(void)
{
    uint64_t cur;
    if (rr_mode != RR_RECORD || rr_record_until == 0) {
        return;
    }
    cur = rr_get_guest_instr_count();
    if (cur < rr_record_until) {
        return;
    }
    rr_finish_record_log();   /* sets rr_mode = RR_OFF */
    rr_record_done = 1;
    info_report("RR: bounded record complete at %llu guest instrs (cap %llu)",
                (unsigned long long)cur, (unsigned long long)rr_record_until);
}

int rr_do_begin_record(const char *name)
{
    Error *err = NULL;
    char snp[1100];
    char log[1100];
    uint64_t reserved = 0;

    if (rr_mode != RR_OFF) {
        error_report("RR: already recording or replaying");
        return -1;
    }
    pstrcpy(rr_name, sizeof(rr_name), name);
    snprintf(snp, sizeof(snp), "%s-rr-snp", name);
    snprintf(log, sizeof(log), "%s-rr-nondet.log", name);

    vm_stop(RUN_STATE_SAVE_VM);

    if (panda_rr_savevm_to_file(snp, &err) < 0) {
        error_report("RR: snapshot to %s failed: %s", snp,
                     err ? error_get_pretty(err) : "unknown");
        if (err) {
            error_free(err);
        }
        vm_start();
        return -1;
    }

    rr_nondet_log = fopen(log, "wb");
    if (!rr_nondet_log) {
        error_report("RR: cannot open nondet log %s", log);
        vm_start();
        return -1;
    }
    /* Reserve 8 bytes at offset 0 for the final instr count (backpatched at end). */
    fwrite(&reserved, sizeof(reserved), 1, rr_nondet_log);

    rr_reset_count();
    rr_record_done = 0;
    rr_mode = RR_RECORD;
    vm_start();
    return 0;
}

int rr_do_end_record(void)
{
    if (rr_mode != RR_RECORD) {
        error_report("RR: not recording");
        return -1;
    }
    /* Quiesce the vCPU so it cannot be inside a capture hook (rr_record_*)
     * while we close the nondet log on the main-loop thread (avoids UAF). */
    vm_stop(RUN_STATE_SAVE_VM);

    rr_finish_record_log();
    vm_start();
    return 0;
}

int rr_do_begin_replay(const char *name)
{
    Error *err = NULL;
    char snp[1100];
    char log[1100];
    uint64_t final_count = 0;

    if (rr_mode != RR_OFF) {
        error_report("RR: already recording or replaying");
        return -1;
    }
    pstrcpy(rr_name, sizeof(rr_name), name);
    snprintf(snp, sizeof(snp), "%s-rr-snp", name);
    snprintf(log, sizeof(log), "%s-rr-nondet.log", name);

    rr_nondet_log = fopen(log, "rb");
    if (!rr_nondet_log) {
        error_report("RR: cannot open nondet log %s", log);
        return -1;
    }
    if (fread(&final_count, sizeof(final_count), 1, rr_nondet_log) != 1) {
        error_report("RR: nondet log %s is truncated", log);
        fclose(rr_nondet_log);
        rr_nondet_log = NULL;
        return -1;
    }
    rr_final_count = final_count;
    if (rr_replay_load_entries() < 0) {
        error_report("RR: failed to load nondet log entries from %s", log);
        fclose(rr_nondet_log);
        rr_nondet_log = NULL;
        return -1;
    }

    vm_stop(RUN_STATE_RESTORE_VM);
    if (panda_rr_loadvm_from_file(snp, &err) < 0) {
        error_report("RR: loadvm from %s failed: %s", snp,
                     err ? error_get_pretty(err) : "unknown");
        if (err) {
            error_free(err);
        }
        fclose(rr_nondet_log);
        rr_nondet_log = NULL;
        return -1;
    }

    rr_reset_count();
    rr_mode = RR_REPLAY;
    info_report("RR: replay snapshot restored; recorded length = %" PRIu64
                " guest instrs", final_count);
    vm_start();
    return 0;
}

int rr_do_end_replay(void)
{
    if (rr_mode != RR_REPLAY) {
        error_report("RR: not replaying");
        return -1;
    }
    vm_stop(RUN_STATE_RESTORE_VM);
    if (rr_nondet_log) {
        fclose(rr_nondet_log);
        rr_nondet_log = NULL;
    }
    rr_mode = RR_OFF;
    vm_start();
    return 0;
}

/* ------------------------- REPLAY: interrupts (3b) ------------------------ */
/* For each entry index, the guest-instr count of the next INTERRUPT_REQUEST
 * (or END_OF_LOG) at or after it. Lets the exec loop clamp a TB so it stops
 * exactly on the recorded interrupt boundary. */
/* Called at the top of cpu_handle_interrupt during replay: drive
 * cpu->interrupt_request entirely from the log. Masks any live device IRQ
 * (force 0) except exactly at a recorded interrupt's prog point, where the
 * recorded interrupt_request value is injected. */
void rr_replay_set_interrupt_request(void *cpu_)
{
    CPUState *cpu = (CPUState *)cpu_;
    uint32_t v = 0;
    if (!rr_diverged && rr_idx < rr_nentries) {
        RR_entry *e = &rr_entries[rr_idx];
        if (e->kind == RR_INTERRUPT_REQUEST &&
            e->count == rr_get_guest_instr_count()) {
            v = (uint32_t)e->val;
            rr_idx++;
        }
    }
    cpu->interrupt_request = v;
}

/* REPLAY: is the next unconsumed log entry an interrupt due at the current prog
 * point? Used to wake a halted vCPU deterministically from the log (no live
 * timer in Model A); the recorded wake interrupt is tagged with the halt's
 * frozen instruction count. */
int rr_replay_interrupt_due(void)
{
    if (rr_diverged || rr_idx >= rr_nentries) {
        return 0;
    }
    return rr_entries[rr_idx].kind == RR_INTERRUPT_REQUEST &&
           rr_entries[rr_idx].count == rr_get_guest_instr_count();
}

/* Instructions to execute before the next recorded interrupt boundary. */
uint64_t rr_num_instr_before_next_interrupt(void)
{
    uint64_t cur, nc;
    if (rr_idx >= rr_nentries || !rr_next_int_count) {
        return (uint64_t)-1;
    }
    cur = rr_get_guest_instr_count();
    nc = rr_next_int_count[rr_idx];
    return nc > cur ? nc - cur : 0;
}

void rr_replay_mark_complete(void)
{
    if (rr_mode == RR_REPLAY) {
        info_report("RR REPLAY COMPLETE: reached final count %llu with NO "
                    "divergence (replayed_pulls=%llu)",
                    (unsigned long long)rr_final_count,
                    (unsigned long long)rr_replayed_pulls);
        rr_mode = RR_OFF;
    }
}

/* ----------------------- device->RAM DMA (Inc 4) -------------------------- */
/* RECORD: a device wrote guest RAM (DMA) outside CPU context. Logged as a
 * RR_SKIPPED_CALL: instr_count|kind|callsite|addr(8)|len(4)|bytes(len). */
void rr_record_dma_write(uint64_t addr, const uint8_t *buf, uint32_t len)
{
    uint64_t ic;
    uint8_t k = (uint8_t)RR_SKIPPED_CALL, cs = 0;
    if (!rr_nondet_log || len == 0) {
        return;
    }
    ic = rr_get_guest_instr_count();
    flockfile(rr_nondet_log);
    fwrite(&ic, sizeof(ic), 1, rr_nondet_log);
    fwrite(&k, 1, 1, rr_nondet_log);
    fwrite(&cs, 1, 1, rr_nondet_log);
    fwrite(&addr, sizeof(addr), 1, rr_nondet_log);
    fwrite(&len, sizeof(len), 1, rr_nondet_log);
    fwrite(buf, len, 1, rr_nondet_log);
    funlockfile(rr_nondet_log);
}

/* REPLAY: apply any recorded device->RAM DMA writes due at the current prog
 * point (devices do not run in replay, so we inject their RAM effects). */
void rr_replay_apply_dma(void)
{
    uint64_t cur = rr_get_guest_instr_count();
    while (!rr_diverged && rr_idx < rr_nentries) {
        RR_entry *e = &rr_entries[rr_idx];
        if (e->kind != RR_SKIPPED_CALL) {
            break;
        }
        if (e->count > cur) {
            break;
        }
        if (e->dma_len) {
            cpu_physical_memory_write(e->dma_addr, e->dma_buf, e->dma_len);
        }
        rr_idx++;
    }
}

/* ---------------------------- HMP control plane ---------------------------- */

void hmp_begin_record(Monitor *mon, const QDict *qdict)
{
    const char *name = qdict_get_str(qdict, "filename");
    uint64_t count = qdict_get_try_int(qdict, "count", 0);
    rr_record_set_until(count);
    if (rr_do_begin_record(name) == 0) {
        if (count) {
            monitor_printf(mon, "RR: recording to %s-rr-snp + %s-rr-nondet.log "
                           "(auto-stop at %llu guest instrs)\n", name, name,
                           (unsigned long long)count);
        } else {
            monitor_printf(mon, "RR: recording to %s-rr-snp + %s-rr-nondet.log\n",
                           name, name);
        }
    } else {
        monitor_printf(mon, "RR: begin_record failed\n");
    }
}

void hmp_end_record(Monitor *mon, const QDict *qdict)
{
    uint64_t n = rr_get_guest_instr_count();
    if (rr_do_end_record() == 0) {
        monitor_printf(mon, "RR: recording stopped at %" PRIu64 " guest instrs\n", n);
    } else {
        monitor_printf(mon, "RR: end_record failed\n");
    }
}

void hmp_begin_replay(Monitor *mon, const QDict *qdict)
{
    const char *name = qdict_get_str(qdict, "filename");
    if (rr_do_begin_replay(name) == 0) {
        monitor_printf(mon, "RR: replaying %s\n", name);
    } else {
        monitor_printf(mon, "RR: begin_replay failed\n");
    }
}

void hmp_end_replay(Monitor *mon, const QDict *qdict)
{
    if (rr_do_end_replay() == 0) {
        monitor_printf(mon, "RR: replay stopped\n");
    } else {
        monitor_printf(mon, "RR: end_replay failed\n");
    }
}
