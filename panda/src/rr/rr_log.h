/* PANDA-NG record/replay: log structures + lifecycle API (ported from classic PANDA). */
#ifndef PANDA_RR_LOG_H
#define PANDA_RR_LOG_H

#include <stdint.h>
#include "exec/rr_record.h"  /* RR_mode, rr_mode, rr_in_record(), record writers */
#include "rr_types.h"          /* RR_log_entry_kind, RR_skipped_call_kind */

/* The program point is solely the guest instruction count (the RR clock). */
typedef struct RR_prog_point_t {
    uint64_t guest_instr_count;
} RR_prog_point;

typedef struct {
    RR_prog_point prog_point;
    RR_log_entry_kind kind;
    uint8_t callsite_loc;
} RR_header;

typedef struct rr_log_entry_t {
    RR_header header;
    union {
        uint8_t  input_1;
        uint16_t input_2;
        uint32_t input_4;
        uint64_t input_8;
        int32_t  interrupt_request;
        uint16_t exit_request;
        int32_t  exception_index;
    } variant;
    struct rr_log_entry_t *next;
} RR_log_entry;

/* prog-point clock (reads first_cpu->rr_guest_instr_count). */
uint64_t rr_get_guest_instr_count(void);
RR_mode  rr_get_mode(void);

/* Lifecycle. name is the recording basename; files are name-rr-snp + name-rr-nondet.log. */
int rr_do_begin_record(const char *name);
int rr_do_end_record(void);
int rr_do_begin_replay(const char *name);
int rr_do_end_replay(void);

#endif /* PANDA_RR_LOG_H */
