#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot efency fork benchmark results: wall time per mode.
#
# Usage:
#   ./plot_efency_fork.py
#   ./plot_efency_fork.py -i /mydata/efency/results/fork_results.json
#   ./plot_efency_fork.py -o ../figures/efency_fork.pdf

import argparse
import os
import sys

import numpy as np

from bench_lib import BenchResults, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart, results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../../efency/results/fork_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/efency_fork.pdf")

SERIES_ORDER = ["glibc", "efence", "efency_sigbus", "efency_handler", "ebpfency"]
SERIES_LABELS = {
    "glibc":          "glibc",
    "efence":         "Electric Fence",
    "efency_sigbus":  "efency (SIGBUS)",
    "efency_handler": "efency (handler)",
    "ebpfency":       "ebpfency",
}
SERIES_COLORS = {
    "glibc":          "steelblue",
    "efence":         "firebrick",
    "efency_sigbus":  "darkorange",
    "efency_handler": "mediumpurple",
    "ebpfency":       "forestgreen",
}


def main():
    parser = argparse.ArgumentParser(
        description="Plot fork benchmark results")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    parser.add_argument("--modes", nargs="+", default=None,
                        help="Override mode order")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    series_order = args.modes or SERIES_ORDER
    y_fn = lambda r: r["wall_ms"]

    # Print summary table
    print(f"\n  {'Mode':<22s} {'Wall time (ms)':>14s}", file=sys.stderr)
    print(f"  {'─' * 22} {'─' * 14}", file=sys.stderr)
    for mode in series_order:
        raw = results_select(results, {"mode": mode}, y_fn)
        if not raw:
            continue
        mean = np.mean(raw)
        std = np.std(raw)
        sl = SERIES_LABELS.get(mode, mode)
        print(f"  {sl:<22s} {mean:>10.1f} +/- {std:.1f}", file=sys.stderr)
    print(file=sys.stderr)

    # Use plot_grouped_bar_chart with mode as groups, single series
    plot_grouped_bar_chart(
        results,
        group_field="mode",
        series_field="name",
        y_select_fn=y_fn,
        output=args.output,
        group_order=series_order,
        group_labels={m: SERIES_LABELS.get(m, m).replace(" ", "\n")
                      for m in series_order},
        series_order=["fork_bench"],
        series_labels={"fork_bench": "fork (200 iterations)"},
        series_colors={"fork_bench": "steelblue"},
        y_label="Wall time (ms)",
        fontsize=22,
        label_fontsize=28,
        legend_fontsize=18,
        figsize=(10, 6),
        grid=False,
        error_bars=False,
        log_scale=True,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
