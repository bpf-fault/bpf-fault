#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot scalability benchmark results: wall time vs thread count.
#
# Usage:
#   ./plot_scale.py                                         # defaults
#   ./plot_scale.py -i ../results/scale_results.json        # custom input
#   ./plot_scale.py -o ../figures/scale.pdf                 # custom output

import argparse
import os
import sys

from bench_lib import BenchResults, parse_results_file
from bench_plot_lib import plot_line_chart

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/scale_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/scale_motivation.pdf")


def main():
    parser = argparse.ArgumentParser(description="Plot scalability results")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)
    pages = results[0].config.get("pages_per_thread", "?")

    plot_line_chart(
        results,
        series_field="mode",
        x_field="threads",
        y_select_fn=lambda r: r["wall_ns"],
        y_transform=lambda ns: ns / 1e6,
        output=args.output,
        series_order=["uffd", "sigsegv", "baseline", ],
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
        x_label="Threads",
        y_label="Time (ms)",
        xscale_log2=False,
        fontsize=20,
        label_fontsize=24,
        legend_fontsize=20,
        linewidth=3,
        markersize=9,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
