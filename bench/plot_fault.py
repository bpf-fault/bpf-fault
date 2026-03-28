#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot single-threaded fault benchmark results: latency by fault type.
#
# When results contain both read and write access modes, missing faults
# are shown for both modes while wp and minor use write-fault only.
# This produces a single combined plot.
#
# Usage:
#   ./plot_fault.py                                          # defaults
#   ./plot_fault.py -i ../results/fault_results.json         # custom input
#   ./plot_fault.py -o ../figures/fault.pdf                  # custom output

import argparse
import os
import sys

import numpy as np

from bench_lib import BenchResults, BenchRun, parse_results_file
from bench_plot_lib import (
    plot_grouped_bar_chart,
    config_combinations,
    results_select,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/fault_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/fault_motivation.pdf")

SERIES_ORDER = ["uffd", "sigsegv", "baseline"]
SERIES_LABELS = {
    "uffd":     "userfaultfd",
    "sigsegv":  "mprotect()+SIGSEGV",
    "baseline": "Baseline (kernel)",
    "bpf":      "bpf_fault",
}
SERIES_COLORS = {
    "uffd":     "darkorange",
    "sigsegv":  "firebrick",
    "baseline": "steelblue",
    "bpf":      "forestgreen",
}


def has_access_field(results):
    """Check if results have an 'access' config field."""
    return any("access" in r.config for r in results)


def build_combined_results(results):
    """Build results with a synthetic 'group' field.

    Missing faults: include both read and write as separate groups.
    WP / minor faults: include write only.

    Returns (results_with_group, group_order, group_labels).
    """
    combined = []
    for r in results:
        ft = r.config.get("fault_type")
        access = r.config.get("access", "write")

        if ft == "missing":
            # Include both read and write
            group = f"missing_{access}"
        else:
            # Only include write
            if access != "write":
                continue
            group = ft

        new_config = dict(r.config)
        new_config["group"] = group
        combined.append(BenchRun(new_config, r.results))

    group_order = ["missing_read", "missing_write", "wp", "minor"]
    group_labels = {
        "missing_read":  "Missing\n(read)",
        "missing_write": "Missing\n(write)",
        "wp":            "Write-Protect",
        "minor":         "Minor",
    }
    # For printing (no newlines)
    group_labels_flat = {
        "missing_read":  "Missing (read)",
        "missing_write": "Missing (write)",
        "wp":            "Write-Protect",
        "minor":         "Minor",
    }

    return combined, group_order, group_labels, group_labels_flat


def build_legacy_results(results):
    """Build results for old data without access field.

    Injects a 'group' field matching fault_type.
    """
    combined = []
    for r in results:
        new_config = dict(r.config)
        new_config["group"] = r.config.get("fault_type")
        combined.append(BenchRun(new_config, r.results))

    group_order = ["missing", "wp", "minor"]
    group_labels = {
        "missing": "Missing",
        "wp":      "Write-\nProtect",
        "minor":   "Minor",
    }
    group_labels_flat = {
        "missing": "Missing",
        "wp":      "Write-Protect",
        "minor":   "Minor",
    }

    return combined, group_order, group_labels, group_labels_flat


def print_latencies(results, group_order, group_labels_flat):
    y_select_fn = lambda r: r["latency_ns"]["avg"]
    y_transform = lambda ns: ns / 1e3

    print(f"\nAverage latencies:", file=sys.stderr)
    print(f"  {'Fault Type':<22s} {'Mode':<22s} {'Latency (µs)':>14s}",
          file=sys.stderr)
    print(f"  {'─' * 22} {'─' * 22} {'─' * 14}", file=sys.stderr)

    for group_val in group_order:
        for series_val in SERIES_ORDER:
            raw = results_select(
                results,
                {"group": group_val, "mode": series_val},
                y_select_fn,
            )
            if not raw:
                continue
            raw = [y_transform(v) for v in raw]
            mean = np.mean(raw)
            gl = group_labels_flat.get(group_val, group_val)
            sl = SERIES_LABELS.get(series_val, series_val)
            print(f"  {gl:<22s} {sl:<22s} {mean:>13.2f}",
                  file=sys.stderr)
    print(file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Plot fault benchmark results")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    if has_access_field(results):
        combined, group_order, group_labels, group_labels_flat = \
            build_combined_results(results)
    else:
        combined, group_order, group_labels, group_labels_flat = \
            build_legacy_results(results)

    print_latencies(combined, group_order, group_labels_flat)

    plot_grouped_bar_chart(
        combined,
        group_field="group",
        series_field="mode",
        y_select_fn=lambda r: r["latency_ns"]["avg"],
        y_transform=lambda ns: ns / 1e3,
        output=args.output,
        group_order=group_order,
        group_labels=group_labels,
        series_order=SERIES_ORDER,
        series_labels=SERIES_LABELS,
        series_colors=SERIES_COLORS,
        y_label="Latency (µs)",
        fontsize=26,
        label_fontsize=34,
        legend_fontsize=24,
        error_bars=False,
        ylimit=18,
        grid=False,
    )
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
