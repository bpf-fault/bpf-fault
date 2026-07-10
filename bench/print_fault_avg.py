#!/usr/bin/env python3
# Print average and p99 latency for each workload in fault results,
# averaged across rounds.
#
# Usage:
#   ./print_fault_avg.py
#   ./print_fault_avg.py -i ../results/fault_results.json

import argparse
import os
import sys
from collections import defaultdict

from bench_lib import BenchResults, parse_results_file

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/fault_results.json")


def main():
    parser = argparse.ArgumentParser(
        description="Print avg and p99 latency per workload")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    # Group by (fault_type, mode, access), averaging across rounds
    groups = defaultdict(list)
    for r in results:
        c = r.config
        key = (c.get("fault_type", ""), c.get("mode", ""), c.get("access", "write"))
        groups[key].append(r.results)

    # Sort: fault_type, then mode, then access
    sorted_keys = sorted(groups.keys())

    hdr = f"{'Fault Type':<14s} {'Mode':<14s} {'Access':<8s} {'Rounds':>6s} {'Avg (µs)':>10s} {'P99 (µs)':>10s}"
    sep = f"{'─'*14} {'─'*14} {'─'*8} {'─'*6} {'─'*10} {'─'*10}"
    print(hdr)
    print(sep)

    for key in sorted_keys:
        fault_type, mode, access = key
        entries = groups[key]
        n = len(entries)
        avg_lat = sum(e["latency_ns"]["avg"] for e in entries) / n / 1e3
        p99_lat = sum(e["latency_ns"]["p99"] for e in entries) / n / 1e3
        print(f"{fault_type:<14s} {mode:<14s} {access:<8s} {n:>6d} {avg_lat:>10.2f} {p99_lat:>10.2f}")


if __name__ == "__main__":
    main()
