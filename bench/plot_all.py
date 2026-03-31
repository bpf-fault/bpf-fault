#!/usr/bin/env python3
"""Master script: produce all benchmark figures in one invocation.

Outputs (all in bench/results/):
  graph1_downtime.png      — VM downtime: full vs. live (UFFD) by config
  graph2_total_time.png    — Total snapshot time: full vs. live (UFFD) by config
  graph4_throughput.png    — Avg throughput during snapshot: FC vs. QEMU
  graph4_latency.png       — Avg latency during snapshot: FC vs. QEMU

Usage (zero-arg from bench/):
    python3 plot_all.py
"""

import os
import sys

_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BENCH_DIR)

import plot_graph4    # noqa: E402
import plot_graphs12  # noqa: E402


def main():
    print("=== Graphs 1 & 2: Downtime / Total Time ===")
    plot_graphs12.main()

    print("\n=== Graph 4: Throughput / Latency ===")
    plot_graph4.main()

    print("\nAll figures written to:", os.path.join(_BENCH_DIR, "results"))


if __name__ == "__main__":
    main()
