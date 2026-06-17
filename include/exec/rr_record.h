/*
 * PANDA-NG record/replay: public record-side interface shared between the RR
 * core (panda/src/rr) and the QEMU capture sites (physmem.c, cpu-exec.c,
 * target/i386 helpers). Canonical home of RR_mode + the global rr_mode.
 */
#ifndef EXEC_RR_RECORD_H
#define EXEC_RR_RECORD_H

#include <stdint.h>

typedef enum { RR_OFF = 0, RR_RECORD, RR_REPLAY } RR_mode;

extern volatile RR_mode rr_mode;

static inline int rr_off(void)       { return rr_mode == RR_OFF; }
static inline int rr_on(void)        { return rr_mode != RR_OFF; }
static inline int rr_in_record(void) { return rr_mode == RR_RECORD; }
static inline int rr_in_replay(void) { return rr_mode == RR_REPLAY; }

/* Record-side writers (WS-1 Increment 2). Tagged with the current guest
 * instruction count (prog point) at write time. */
void rr_record_input_1(uint8_t val);
void rr_record_input_2(uint16_t val);
void rr_record_input_4(uint32_t val);
void rr_record_input_8(uint64_t val);
void rr_record_io_read(uint64_t val, unsigned size);
void rr_record_interrupt_request(int interrupt_request);
void rr_record_exception_index(int exception_index);

/* Replay-side (WS-1 Increment 3). */
void rr_replay_input_1(uint8_t *val);
void rr_replay_input_2(uint16_t *val);
void rr_replay_input_4(uint32_t *val);
void rr_replay_input_8(uint64_t *val);
void rr_replay_io_read(uint64_t *val, unsigned size);
int  rr_replay_finished(void);
int  rr_replay_diverged(void);
uint64_t rr_get_guest_instr_count(void);
void rr_replay_set_interrupt_request(void *cpu);
uint64_t rr_num_instr_before_next_interrupt(void);
void rr_replay_mark_complete(void);
int  rr_replay_interrupt_due(void);
void rr_record_dma_write(uint64_t addr, const uint8_t *buf, uint32_t len);
void rr_replay_apply_dma(void);

/* Bounded recording: instruction-count cap for tractable RR debugging.
 * 0 = unbounded (classic stop/end_record behavior). When >0, set BEFORE
 * begin_record; recording auto-finalizes (writes END_OF_LOG, backpatches the
 * final count, closes the log, rr_mode->RR_OFF) once the guest instruction
 * count reaches the cap. rr_record_check_bound() is the per-TB hook called
 * from the cpu-exec loop; it runs on the vCPU thread where capture hooks also
 * run, so there is no concurrent writer to the nondet log. */
void rr_record_set_until(uint64_t count);
uint64_t rr_record_get_until(void);
int  rr_record_bounded_done(void);
void rr_record_check_bound(void);

#endif /* EXEC_RR_RECORD_H */
