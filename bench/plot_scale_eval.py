#!/usr/bin/env python3
# Plot scalability benchmark results: bpf_fault vs baseline vs uffd.
#
# Usage:
#   ./plot_scale_eval.py                                         # defaults
#   ./plot_scale_eval.py -i ../results/scale_results.json        # custom input
#   ./plot_scale_eval.py -o ../figures/scale_eval.pdf            # custom output

import argparse
import os
import sys

from bench_lib import BenchResults, parse_results_file
from bench_plot_lib import plot_line_chart

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/scale_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/scale_eval.pdf")


def main():
    parser = argparse.ArgumentParser(description="Plot scalability: bpf vs baseline vs uffd")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    # The reused results file can accumulate runs with different page or
    # CPU counts, which would get averaged together below.
    for field in ("pages_per_thread", "cpus"):
        values = {r.config.get(field) for r in results}
        if len(values) > 1:
            print(f"warning: results mix multiple {field} values "
                  f"({sorted(values, key=str)}), averaging across them",
                  file=sys.stderr)

    plot_line_chart(
        results,
        series_field="mode",
        x_field="threads",
        y_select_fn=lambda r: r["wall_ns"],
        y_transform=lambda ns: ns / 1e6,
        output=args.output,
        series_order=["uffd", "bpf", "baseline"],
        series_labels={
            "baseline":  "Baseline (kernel)",
            "bpf":       "bpf_fault",
            "uffd":      "userfaultfd",
        },
        series_colors={
            "baseline":  "steelblue",
            "bpf":       "forestgreen",
            "uffd":      "darkorange",
        },
        x_label="Threads",
        y_label="Run time (ms)",
        xscale_log2=False,
        yscale_log=True,
        fontsize=30,
        label_fontsize=38,
        legend_fontsize=24,
        linewidth=6,
        markersize=15,
        error_bars=False,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
