#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot efency benchmark results: two figures, microbenchmarks and applications,
# both normalized to glibc baseline.
#
# Usage:
#   ./plot_efency_throughput.py
#   ./plot_efency_throughput.py -i /mydata/efency/results/malloc_results.json
#   ./plot_efency_throughput.py --apps-input /mydata/efency/results/app_results.json
#   ./plot_efency_throughput.py --modes glibc efency_sigbus efency_handler ebpfency

import argparse
import os
import sys

import numpy as np

from bench_lib import BenchResults, BenchRun, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart, results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MICRO_INPUT = os.path.join(SCRIPT_DIR, "../../efency/results/malloc_results.json")
DEFAULT_APPS_INPUT = os.path.join(SCRIPT_DIR, "../../efency/results/app_results.json")
DEFAULT_OUTPUT_MICRO = os.path.join(SCRIPT_DIR, "../figures/efency_micro.pdf")
DEFAULT_OUTPUT_APPS = os.path.join(SCRIPT_DIR, "../figures/efency_apps.pdf")

# --- Series (allocator modes) ---

SERIES_ORDER = ["efence", "efency_handler", "efency_sigbus", "ebpfency"]
SERIES_LABELS = {
    "glibc":          "glibc",
    "efence":         "Electric Fence",
    "efency_sigbus":  "efency (SIGBUS)",
    "efency_handler": "efency (handler)",
    "ebpfency":       "efency (bpf_fault)",
}
SERIES_COLORS = {
    "glibc":          "steelblue",
    "efence":         "steelblue",
    "efency_handler": "darkorange",
    "efency_sigbus":  "firebrick",
    "ebpfency":       "forestgreen",
}

# --- Microbenchmark groups: (bench_name, size) ---

MICRO_GROUPS = [
    ("seq_malloc_free", 128),
    ("alloc_no_touch", 128),
    ("speculative_10pct", 64),
    ("speculative_50pct", 64),
    ("speculative_100pct", 64),
    ("mt_no_touch", 64),
]
MICRO_GROUP_LABELS = {
    "seq_malloc_free_128":   "seq m/f\n(128B)",
    "alloc_no_touch_128":    "no touch\n(128B)",
    "speculative_10pct_64":  "specul.\n10%",
    "speculative_50pct_64":  "specul.\n50%",
    "speculative_100pct_64": "specul.\n100%",
    "mt_no_touch_64":        "mt no\ntouch",
}

# --- Application groups ---

APP_GROUPS = ["clang", "ripgrep", "git_status", "python", "jq"]
APP_GROUP_LABELS = {
    "clang":      "clang",
    "ripgrep":    "ripgrep",
    "git_status": "git\nstatus",
    "python":     "python",
    "jq":         "jq",
}


def normalize_group(results, config_match, y_fn, group_name,
                    series_order, baseline="glibc"):
    """Normalize results for one group to baseline, return BenchRun list."""
    baseline_match = dict(config_match, mode=baseline)
    baseline_vals = results_select(results, baseline_match, y_fn)
    if not baseline_vals:
        return []
    baseline_mean = np.mean(baseline_vals)
    if baseline_mean <= 0:
        return []

    out = []
    for mode in series_order:
        mode_match = dict(config_match, mode=mode)
        vals = results_select(results, mode_match, y_fn)
        for v in vals:
            out.append(BenchRun(
                {"group": group_name, "mode": mode},
                BenchResults({"overhead": v / baseline_mean}),
            ))
    return out


def print_table(title, groups, group_labels, combined, series_order):
    """Print summary table to stderr."""
    y_fn = lambda r: r["overhead"]

    print(f"\n  {title}", file=sys.stderr)
    print(f"  {'Benchmark':<22s} {'Mode':<22s} {'overhead':>10s}",
          file=sys.stderr)
    print(f"  {'─' * 22} {'─' * 22} {'─' * 10}", file=sys.stderr)

    for group in groups:
        gl = group_labels.get(group, group).replace('\n', ' ')
        for mode in series_order:
            raw = results_select(combined, {"group": group, "mode": mode}, y_fn)
            if not raw:
                continue
            mean = np.mean(raw)
            sl = SERIES_LABELS.get(mode, mode)
            print(f"  {gl:<22s} {sl:<22s} {mean:>10.1f}x", file=sys.stderr)
    print(file=sys.stderr)


def plot_figure(combined, group_order, group_labels, series_order, output,
                figsize=(10, 6), log_scale=True, hlines=None, ylimit_top=None,
                legend_loc="best"):
    """Plot one normalized grouped bar chart."""
    active_groups = [g for g in group_order
                     if any(r.config["group"] == g for r in combined)]
    if not active_groups:
        print(f"  No data for {output}, skipping", file=sys.stderr)
        return

    plot_grouped_bar_chart(
        combined,
        group_field="group",
        series_field="mode",
        y_select_fn=lambda r: r["overhead"],
        output=output,
        group_order=active_groups,
        group_labels=group_labels,
        series_order=series_order,
        series_labels=SERIES_LABELS,
        series_colors=SERIES_COLORS,
        y_label="Overhead (× vs glibc)",
        fontsize=22,
        label_fontsize=28,
        legend_fontsize=20,
        figsize=figsize,
        grid=False,
        error_bars=False,
        log_scale=log_scale,
        hlines=hlines,
        ylimit_top=ylimit_top,
        legend_loc=legend_loc,
    )
    print(f"Plot saved to {output}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Plot efency benchmark results")
    parser.add_argument("-i", "--input", default=DEFAULT_MICRO_INPUT,
                        help="Microbenchmark JSON results file")
    parser.add_argument("--apps-input", default=DEFAULT_APPS_INPUT,
                        help="Application benchmark JSON results file")
    parser.add_argument("--output-micro", default=DEFAULT_OUTPUT_MICRO,
                        help="Output PDF for microbenchmarks")
    parser.add_argument("--output-apps", default=DEFAULT_OUTPUT_APPS,
                        help="Output PDF for applications")
    parser.add_argument("--modes", nargs="+", default=None,
                        help="Override series order (mode names)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    micro_results = parse_results_file(args.input, BenchResults)

    app_results = []
    if os.path.isfile(args.apps_input):
        app_results = parse_results_file(args.apps_input, BenchResults)
    else:
        print(f"warning: {args.apps_input} not found, skipping app benchmarks",
              file=sys.stderr)

    series_order = args.modes or SERIES_ORDER

    # --- Microbenchmarks ---
    micro_combined = []
    micro_group_order = []
    for bench, size in MICRO_GROUPS:
        group_name = f"{bench}_{size}"
        micro_group_order.append(group_name)
        micro_combined.extend(normalize_group(
            micro_results, {"bench": bench, "size": size},
            lambda r: r["ns_per_op"], group_name, series_order,
        ))

    if micro_combined:
        print_table("Microbenchmarks", micro_group_order,
                    MICRO_GROUP_LABELS, micro_combined, series_order)
        plot_figure(micro_combined, micro_group_order, MICRO_GROUP_LABELS,
                    series_order, args.output_micro, ylimit_top=1000000,
                    legend_loc="upper left")

    # --- Applications (no glibc/efence — just the three efency modes) ---
    app_series = [s for s in series_order
                  if s not in ("glibc", "efence")]
    app_combined = []
    for app in APP_GROUPS:
        app_combined.extend(normalize_group(
            app_results, {"app": app},
            lambda r: r["wall_ms"], app, app_series,
        ))

    if app_combined:
        print_table("Applications", APP_GROUPS,
                    APP_GROUP_LABELS, app_combined, app_series)
        plot_figure(app_combined, APP_GROUPS, APP_GROUP_LABELS,
                    app_series, args.output_apps,
                    log_scale=True, ylimit_top=150,
                    hlines=[{"y": 1.0, "color": SERIES_COLORS["glibc"],
                             "label": "glibc (1.0×)"}])


if __name__ == "__main__":
    main()
