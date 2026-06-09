/* PANDA-NG record/replay: shared type/enum definitions (ported from classic PANDA). */
#ifndef PANDA_RR_TYPES_H
#define PANDA_RR_TYPES_H

#include <stdint.h>

/* Nondeterministic-input log entry kinds (on-disk tag, do not renumber). */
typedef enum {
    RR_INPUT_1,
    RR_INPUT_2,
    RR_INPUT_4,
    RR_INPUT_8,
    RR_INTERRUPT_REQUEST,
    RR_EXIT_REQUEST,
    RR_SKIPPED_CALL,
    RR_END_OF_LOG,
    RR_PENDING_INTERRUPTS,
    RR_EXCEPTION,
    RR_LAST
} RR_log_entry_kind;

/* Device side-effect ("skipped call") kinds replayed without re-running the device. */
typedef enum {
    RR_CALL_CPU_MEM_RW,
    RR_CALL_MEM_REGION_CHANGE,
    RR_CALL_CPU_MEM_UNMAP,
    RR_CALL_HD_TRANSFER,
    RR_CALL_NET_TRANSFER,
    RR_CALL_HANDLE_PACKET,
    RR_CALL_LAST
} RR_skipped_call_kind;

#endif /* PANDA_RR_TYPES_H */
