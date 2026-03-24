#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot single-threaded fault benchmark results: throughput by fault type.
#
# Usage:
#   ./plot_fault.py                                          # defaults
#   ./plot_fault.py -i ../results/fault_results.json         # custom input
#   ./plot_fault.py -o ../figures/fault.pdf                  # custom output

import argparse
import os
import sys

from bench_lib import BenchResults, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/fault_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/fault_motivation.pdf")


def main():
    parser = argparse.ArgumentParser(description="Plot fault benchmark results")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    plot_grouped_bar_chart(
        results,
        group_field="fault_type",
        series_field="mode",
        y_select_fn=lambda r: r["latency_ns"]["avg"],
        y_transform=lambda ns: ns / 1e3,
        output=args.output,
        group_order=["missing", "wp", "minor"],
        group_labels={
            "missing": "Missing",
            "wp":      "Write-Protect",
            "minor":   "Minor (shmem)",
        },
        series_order=["uffd", "sigsegv", "baseline"],
        series_labels={
            "uffd":     "userfaultfd",
            "sigsegv":  "mprotect()+SIGSEGV",
            "baseline": "Baseline (kernel)",
            # "bpf":      "bpf_fault",
        },
        series_colors={
            "uffd":     "darkorange",
            "sigsegv":  "firebrick",
            "baseline": "steelblue",
            # "bpf":      "forestgreen",
        },
        y_label="Latency (µs)",
        fontsize=20,
        label_fontsize=24,
        legend_fontsize=20,
        error_bars=False,
        ylimit=15,
        grid=False,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
