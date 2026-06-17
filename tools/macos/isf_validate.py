#!/usr/bin/env python3
import json, sys
d = json.load(open(sys.argv[1]))
print("top keys:", list(d.keys()))
md = d.get("metadata", {})
print("producer:", md.get("producer"))
ut = d.get("user_types", {})
sym = d.get("symbols", {})
print("user_types:", len(ut), "| symbols:", len(sym), "| base_types:", len(d.get("base_types", {})))

print("\n-- key symbols --")
for s in ["kernproc", "allproc", "_kernproc", "_allproc", "processor_list",
          "_processor_list", "kernel_pmap", "_kernel_pmap", "nprocs", "_nprocs",
          "vm_kernel_slide", "_vm_kernel_slide"]:
    if s in sym:
        print("  %-20s addr=0x%x" % (s, sym[s].get("address", 0)))

def fields(t):
    return ut.get(t, {}).get("fields", {})

print("\n-- key structs --")
for t in ["proc", "task", "thread", "vm_map", "vm_map_entry", "queue_entry", "_vm_map"]:
    if t in ut:
        print("  struct %-14s size=%s fields=%d" % (t, ut[t].get("size"), len(fields(t))))
    else:
        print("  struct %-14s MISSING" % t)

print("\n-- proc fields --")
p = fields("proc")
for fn in ["p_list", "p_pid", "p_comm", "p_name", "task", "p_ppid", "p_uid"]:
    if fn in p:
        print("  proc.%-10s @ %s" % (fn, p[fn].get("offset")))

print("\n-- task fields --")
t = fields("task")
for fn in ["map", "tasks", "bsd_info", "threads", "thread_count"]:
    if fn in t:
        print("  task.%-12s @ %s" % (fn, t[fn].get("offset")))
