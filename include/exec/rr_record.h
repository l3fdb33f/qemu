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

#endif /* EXEC_RR_RECORD_H */
