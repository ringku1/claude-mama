#!/usr/bin/env python3
"""How many agents this goal may run at once (the skill dispatches up to these). Linux, macOS, Windows.

Usage: resources.py <ready_steps> [store_dir] [own_slug]
Prints:
  limit      — agents that edit and build: min(cores/2 (halved if busy), free RAM GB / 1.5, 8, ready)
               minus steps other goals are running
  read_limit — read-only agents (research, review, test design; no local load): min(8, ready)
"""
import glob
import os
import re
import subprocess
import sys

CAP = 8


def free_ram_gb():
    """Available memory in GB, or None if this OS can't tell."""
    try:
        if os.path.exists("/proc/meminfo"):  # Linux
            m = re.search(r"MemAvailable:\s+(\d+) kB", open("/proc/meminfo").read())
            return int(m.group(1)) / 1048576 if m else None
        if sys.platform == "darwin":  # free + inactive + speculative pages are available
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
            ps = re.search(r"page size of (\d+)", out)
            pages = sum(int(n) for n in re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", out))
            return pages * int(ps.group(1) if ps else 4096) / 1073741824
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MemoryStatus()
            st.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullAvailPhys / 1073741824
    except Exception:
        pass
    return None


def others_running(store, own):
    """Steps other goals in this store are running right now."""
    n = 0
    for plan in glob.glob(os.path.join(store, "*", "plan.md")):
        if os.path.basename(os.path.dirname(plan)) == own:
            continue
        text = open(plan, encoding="utf-8", errors="ignore").read()
        if not re.search(r"^goal: .*status: running", text, re.M):
            continue
        n += len(re.findall(r"^\| S\d+ .*\| (?:running|testing|fixing) \|", text, re.M))
    return n


def main():
    ready = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    store = sys.argv[2] if len(sys.argv) > 2 else ""
    own = sys.argv[3] if len(sys.argv) > 3 else ""
    cores = os.cpu_count() or 2
    free = free_ram_gb()
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    by_cpu = max(cores // 2, 1)
    if load is not None and load > cores * 0.7:
        by_cpu = max(by_cpu // 2, 1)
    by_ram = max(int(free / 1.5), 1) if free is not None else CAP
    others = others_running(store, own) if store and os.path.isdir(store) else 0
    limit = max(min(by_cpu, by_ram, CAP, ready) - others, 1)
    read_limit = max(min(CAP, ready), 1)
    print(f"limit={limit} read_limit={read_limit} cores={cores} "
          f"free_ram_gb={'?' if free is None else f'{free:.1f}'} load={'?' if load is None else f'{load:.2f}'} "
          f"other_goals_running_steps={others}")


if __name__ == "__main__":
    main()
