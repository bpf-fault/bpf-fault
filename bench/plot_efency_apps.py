#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot efency real-application benchmark results: wall time by app and mode.
#
# Usage:
#   ./plot_efency_apps.py
#   ./plot_efency_apps.py -i /mydata/efency/results/app_results.json
#   ./plot_efency_apps.py -o ../figures/efency_apps.pdf

import argparse
import os
import sys

import numpy as np

from bench_lib import BenchResults, BenchRun, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart, results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../../efency/results/app_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/efency_apps.pdf")

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

GROUP_ORDER = ["gcc", "clang", "git_grep", "ripgrep"]
GROUP_LABELS = {
    "gcc":      "gcc\n(compile)",
    "clang":    "clang\n(compile)",
    "git_grep": "git grep\n(search)",
    "ripgrep":  "ripgrep\n(search)",
}


def main():
    parser = argparse.ArgumentParser(
        description="Plot application benchmark results")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    parser.add_argument("--modes", nargs="+", default=None,
                        help="Override series order (mode names)")
    parser.add_argument("--normalize", action="store_true",
                        help="Normalize to glibc baseline (show slowdown)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    series_order = args.modes or SERIES_ORDER
    y_fn = lambda r: r["wall_ms"]

    # Print summary table
    print(f"\n  {'App':<15s} {'Mode':<22s} {'Wall time (ms)':>14s}",
          file=sys.stderr)
    print(f"  {'─' * 15} {'─' * 22} {'─' * 14}", file=sys.stderr)
    for app in GROUP_ORDER:
        for mode in series_order:
            raw = results_select(results, {"app": app, "mode": mode}, y_fn)
            if not raw:
                continue
            mean = np.mean(raw)
            sl = SERIES_LABELS.get(mode, mode)
            print(f"  {app:<15s} {sl:<22s} {mean:>14.1f}", file=sys.stderr)
    print(file=sys.stderr)

    if args.normalize:
        y_label = "Slowdown vs glibc (x)"
        # Transform: divide by glibc mean for each app
        glibc_means = {}
        for app in GROUP_ORDER:
            raw = results_select(results, {"app": app, "mode": "glibc"}, y_fn)
            if raw:
                glibc_means[app] = np.mean(raw)

        normalized = []
        for r in results:
            app = r.config.get("app")
            if app in glibc_means and glibc_means[app] > 0:
                new_results = BenchResults({"wall_ms": r.results["wall_ms"] / glibc_means[app]})
                normalized.append(BenchRun(r.config, new_results))
        results = normalized
    else:
        y_label = "Wall time (ms)"

    plot_grouped_bar_chart(
        results,
        group_field="app",
        series_field="mode",
        y_select_fn=y_fn,
        output=args.output,
        group_order=GROUP_ORDER,
        group_labels=GROUP_LABELS,
        series_order=series_order,
        series_labels=SERIES_LABELS,
        series_colors=SERIES_COLORS,
        y_label=y_label,
        fontsize=22,
        label_fontsize=28,
        legend_fontsize=18,
        figsize=(12, 6),
        grid=False,
        error_bars=False,
        log_scale=True,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
