#!/usr/bin/env python3
# Plot dynamic linking microbenchmarks: synthetic no-touch (4K, 100K, 1M)
# and dlopen no-access (1M).
#
# Usage:
#   ./plot_dynlink_micro.py
#   ./plot_dynlink_micro.py -i ../results/dynlink/dynlink_results.json
#   ./plot_dynlink_micro.py -o ../figures/dynlink_micro.pdf

import argparse
import os
import statistics
import sys

from bench_lib import BenchResults, BenchRun, parse_results_file
from bench_plot_lib import plot_grouped_bar_chart, results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR,
                             "../results/dynlink/dynlink_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/dynlink_micro.pdf")

MODES = ["std", "bpf"]
MODE_LABELS = {"std": "Standard", "bpf": "bpf_fault"}


def synthetic_ms(results, relocs, mode):
    """Median wall time across rounds of one synthetic configuration."""
    vals = results_select(
        results, {"benchmark": "synthetic", "relocs": relocs, "mode": mode},
        lambda r: r["wall_ms"])
    if not vals:
        print(f"error: no synthetic results for {relocs} relocs ({mode})",
              file=sys.stderr)
        sys.exit(1)
    return statistics.median(vals)


def dlopen_ms(results, mode):
    """Median dlopen time (no access), converted from µs."""
    vals = results_select(
        results,
        {"benchmark": "dlopen", "access": "none", "mode": mode},
        lambda r: r["median_us"])
    if not vals:
        print(f"error: no dlopen results ({mode})", file=sys.stderr)
        sys.exit(1)
    return vals[0] / 1000.0


def build_results(results):
    out = []
    for relocs, label in [(4000, "4K"), (100000, "100K"),
                          (1000000, "1M")]:
        for mode in MODES:
            out.append(BenchRun(
                {"workload": f"{label} relocs", "mode": mode},
                BenchResults({"wall_ms": synthetic_ms(results, relocs,
                                                      mode)})))
    for mode in MODES:
        out.append(BenchRun(
            {"workload": "dlopen 1M", "mode": mode},
            BenchResults({"wall_ms": dlopen_ms(results, mode)})))
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Plot dynamic linking microbenchmarks")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)
    combined = build_results(results)

    # Print summary
    print(f"\n  {'Workload':<20s} {'Mode':<12s} {'Wall (ms)':>10s}",
          file=sys.stderr)
    print(f"  {'─'*20} {'─'*12} {'─'*10}", file=sys.stderr)
    for r in combined:
        print(f"  {r.config['workload']:<20s} "
              f"{MODE_LABELS[r.config['mode']]:<12s} "
              f"{r.results['wall_ms']:>10.2f}", file=sys.stderr)
    print(file=sys.stderr)

    plot_grouped_bar_chart(
        combined,
        group_field="workload",
        series_field="mode",
        y_select_fn=lambda r: r["wall_ms"],
        output=args.output,
        group_order=["4K relocs", "100K relocs", "1M relocs",
                     "dlopen 1M"],
        series_order=MODES,
        series_labels=MODE_LABELS,
        series_colors={"std": "steelblue", "bpf": "forestgreen"},
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
