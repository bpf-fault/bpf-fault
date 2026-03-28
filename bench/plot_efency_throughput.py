#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot efency malloc benchmark throughput: ns/op grouped by benchmark.
#
# Generates two figures:
#   1. Standard benchmarks (efency_throughput.pdf)
#   2. BPF-favoring benchmarks (efency_bpf_throughput.pdf)
#
# Usage:
#   ./plot_efency_throughput.py
#   ./plot_efency_throughput.py -i /mydata/efency/results/malloc_results.json
#   ./plot_efency_throughput.py --no-bpf          # skip BPF-favoring figure

import argparse
import os
import sys

import numpy as np

from bench_lib import BenchResults, BenchRun, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart, results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../../efency/results/malloc_results.json")
DEFAULT_OUTPUT_STD = os.path.join(SCRIPT_DIR, "../figures/efency_throughput.pdf")
DEFAULT_OUTPUT_BPF = os.path.join(SCRIPT_DIR, "../figures/efency_bpf_throughput.pdf")

# --- Series (allocator modes) ---

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

# --- Standard benchmarks: (bench_name, size) pairs to include ---

STD_BENCHMARKS = [
    ("seq_malloc_free", 128),
    ("bulk_alloc_free", 64),
    ("realloc_chain", 4096),
    ("mixed_workload", 256),
    ("multithread_bulk", 64),
]
# Map (bench, size) -> x-axis label; size comes from bench_malloc output
STD_GROUP_LABELS = {
    "seq_malloc_free_128":  "seq m/f\n(128B)",
    "bulk_alloc_free_64":   "bulk m/f\n(64B)",
    "realloc_chain_4096":   "realloc\nchain",
    "mixed_workload_256":   "mixed\nworkload",
    "multithread_bulk_64":  "multi-\nthread",
}

# --- BPF-favoring benchmarks ---

BPF_BENCHMARKS = [
    ("alloc_no_touch", 128),
    ("speculative_10pct", 64),
    ("speculative_50pct", 64),
    ("speculative_100pct", 64),
    ("deferred_total", 64),
    ("mt_no_touch", 64),
]
BPF_GROUP_LABELS = {
    "alloc_no_touch_128":    "no touch\n(128B)",
    "speculative_10pct_64":  "specul.\n10%",
    "speculative_50pct_64":  "specul.\n50%",
    "speculative_100pct_64": "specul.\n100%",
    "deferred_total_64":     "deferred\ntotal",
    "mt_no_touch_64":        "mt no\ntouch",
}


def add_group_field(results, bench_list):
    """Add synthetic 'group' field and filter to only desired benchmarks."""
    wanted = {f"{b}_{s}" for b, s in bench_list}
    combined = []
    for r in results:
        group = f"{r.config['bench']}_{r.config['size']}"
        if group not in wanted:
            continue
        new_config = dict(r.config)
        new_config["group"] = group
        combined.append(BenchRun(new_config, r.results))
    return combined


def print_table(results, bench_list, group_labels):
    """Print summary table to stderr."""
    y_fn = lambda r: r["ns_per_op"]

    print(f"\n  {'Benchmark':<22s} {'Mode':<22s} {'ns/op':>10s}",
          file=sys.stderr)
    print(f"  {'─' * 22} {'─' * 22} {'─' * 10}", file=sys.stderr)

    for bench, size in bench_list:
        group = f"{bench}_{size}"
        gl = group_labels.get(group, group).replace('\n', ' ')
        for mode in SERIES_ORDER:
            raw = results_select(
                results, {"group": group, "mode": mode}, y_fn)
            if not raw:
                continue
            mean = np.mean(raw)
            sl = SERIES_LABELS.get(mode, mode)
            print(f"  {gl:<22s} {sl:<22s} {mean:>10.0f}", file=sys.stderr)
    print(file=sys.stderr)


def plot_figure(results, bench_list, group_labels, output, title=""):
    """Generate one grouped bar chart figure."""
    combined = add_group_field(results, bench_list)
    if not combined:
        print(f"  No data for {output}, skipping", file=sys.stderr)
        return

    group_order = [f"{b}_{s}" for b, s in bench_list]

    print_table(combined, bench_list, group_labels)

    plot_grouped_bar_chart(
        combined,
        group_field="group",
        series_field="mode",
        y_select_fn=lambda r: r["ns_per_op"],
        output=output,
        group_order=group_order,
        group_labels=group_labels,
        series_order=SERIES_ORDER,
        series_labels=SERIES_LABELS,
        series_colors=SERIES_COLORS,
        y_label="Latency (ns/op)",
        fontsize=22,
        label_fontsize=28,
        legend_fontsize=18,
        figsize=(12, 6),
        grid=False,
        error_bars=False,
        log_scale=True,
    )
    print(f"Plot saved to {output}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Plot efency malloc benchmark throughput")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output-std", default=DEFAULT_OUTPUT_STD,
                        help="Output PDF for standard benchmarks")
    parser.add_argument("--output-bpf", default=DEFAULT_OUTPUT_BPF,
                        help="Output PDF for BPF-favoring benchmarks")
    parser.add_argument("--no-bpf", action="store_true",
                        help="Skip BPF-favoring figure")
    parser.add_argument("--modes", nargs="+", default=None,
                        help="Override series order (mode names)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    global SERIES_ORDER
    if args.modes:
        SERIES_ORDER = args.modes

    # Figure 1: Standard benchmarks
    plot_figure(results, STD_BENCHMARKS, STD_GROUP_LABELS, args.output_std)

    # Figure 2: BPF-favoring benchmarks
    if not args.no_bpf:
        plot_figure(results, BPF_BENCHMARKS, BPF_GROUP_LABELS, args.output_bpf)


if __name__ == "__main__":
    main()
