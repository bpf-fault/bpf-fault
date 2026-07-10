#!/usr/bin/env python3
# Plot dynamic linking microbenchmarks: synthetic no-touch (4K, 100K, 1M)
# and dlopen no-access (1M).
#
# Usage:
#   ./plot_dynlink_micro.py
#   ./plot_dynlink_micro.py -o ../figures/dynlink_micro.pdf

import argparse
import os
import re
import sys

from bench_lib import BenchResults, BenchRun
from bench_plot_lib import plot_grouped_bar_chart

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "../results/dynlink")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/dynlink_micro.pdf")


def parse_synthetic(path):
    """Parse synthetic benchmark output, return (std_median_ms, bpf_median_ms)."""
    text = open(path).read()
    std = re.search(r'Standard\s+[\d.]+ms\s+([\d.]+)ms', text)
    bpf = re.search(r'BPF\s+[\d.]+ms\s+([\d.]+)ms', text)
    return float(std.group(1)), float(bpf.group(1))


def parse_dlopen(path):
    """Parse dlopen benchmark, return (std_no_access_us, bpf_no_access_us)."""
    text = open(path).read()
    std = re.search(r'Standard dlopen \(no access\)\s+([\d,]+)\s+([\d,]+)', text)
    bpf = re.search(r'BPF dlopen \(no access\)\s+([\d,]+)\s+([\d,]+)', text)
    std_median = int(std.group(2).replace(',', ''))
    bpf_median = int(bpf.group(2).replace(',', ''))
    return std_median / 1000.0, bpf_median / 1000.0  # convert to ms


def build_results():
    results = []

    for relocs, label in [(4000, "4K"), (100000, "100K"), (1000000, "1M")]:
        path = os.path.join(RESULTS_DIR, f"synthetic_notouch_{relocs}.txt")
        if not os.path.isfile(path):
            print(f"warning: {path} not found, skipping", file=sys.stderr)
            continue
        std_ms, bpf_ms = parse_synthetic(path)
        results.append(BenchRun(
            {"workload": f"{label} relocs", "mode": "Standard"},
            BenchResults({"wall_ms": std_ms})))
        results.append(BenchRun(
            {"workload": f"{label} relocs", "mode": "bpf_fault"},
            BenchResults({"wall_ms": bpf_ms})))

    dlopen_path = os.path.join(RESULTS_DIR, "dlopen_1000000.txt")
    if os.path.isfile(dlopen_path):
        std_ms, bpf_ms = parse_dlopen(dlopen_path)
        results.append(BenchRun(
            {"workload": "dlopen 1M", "mode": "Standard"},
            BenchResults({"wall_ms": std_ms})))
        results.append(BenchRun(
            {"workload": "dlopen 1M", "mode": "bpf_fault"},
            BenchResults({"wall_ms": bpf_ms})))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Plot dynamic linking microbenchmarks")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    results = build_results()
    if not results:
        print("error: no results found", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print(f"\n  {'Workload':<20s} {'Mode':<12s} {'Wall (ms)':>10s}",
          file=sys.stderr)
    print(f"  {'─'*20} {'─'*12} {'─'*10}", file=sys.stderr)
    for r in results:
        print(f"  {r.config['workload'].replace(chr(10),' '):<20s} "
              f"{r.config['mode']:<12s} {r.results['wall_ms']:>10.2f}",
              file=sys.stderr)
    print(file=sys.stderr)

    plot_grouped_bar_chart(
        results,
        group_field="workload",
        series_field="mode",
        y_select_fn=lambda r: r["wall_ms"],
        output=args.output,
        group_order=["4K relocs", "100K relocs", "1M relocs",
                     "dlopen 1M"],
        series_order=["Standard", "bpf_fault"],
        series_labels={"Standard": "Baseline", "bpf_fault": "bpf_fault"},
        series_colors={"Standard": "steelblue", "bpf_fault": "forestgreen"},
        y_label="Startup time (ms)",
        fontsize=20,
        label_fontsize=28,
        legend_fontsize=22,
        legend_loc="upper left",
        figsize=(8, 4.5),
        bar_width=0.7,
        grid=False,
        error_bars=False,
        show_values=True,
        value_fmt="{:.1f}",
        ylimit=22,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
