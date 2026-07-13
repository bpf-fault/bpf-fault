#!/usr/bin/env python3
# Plot dynamic linking steady-state dirty memory across workloads for
# tested applications in a single grouped bar chart.
#
# Usage:
#   ./plot_dynlink_steady.py
#   ./plot_dynlink_steady.py -i ../results/dynlink/dynlink_results.json
#   ./plot_dynlink_steady.py -o ../figures/dynlink_steady.pdf

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

import numpy as np

from bench_lib import BenchResults, parse_results_file
from bench_plot_lib import results_select

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR,
                             "../results/dynlink/dynlink_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/dynlink_steady.pdf")

# (display_label, benchmark, app, workload)
WORKLOADS = [
    ("Clang\n-O0 -c", "app_memory", "clang", "-O0 -c"),
    ("Clang\n-O2 -o", "app_memory", "clang", "-O2 -o"),
    ("Clang\nconfigure", "app_memory", "clang", "configure probe"),
    ("Deno\neval", "app_memory", "deno", "eval"),
    ("Deno\nHTTP", "app_memory", "deno", "HTTP server"),
    ("Chrome\nexample.com", "chrome_memory", None, "example.com"),
    ("Chrome\nPDF", "chrome_memory", None, "local content"),
]


def anon_kb(results, benchmark, app, workload, mode):
    match = {"benchmark": benchmark, "workload": workload, "mode": mode}
    if app is not None:
        match["app"] = app
    vals = results_select(results, match, lambda r: r["anon_kb"])
    return vals[0] if vals else None


def collect_data(results):
    """Return (data, missing): (display_label, std_kb, bpf_kb) tuples and
    a list of what is absent."""
    data = []
    missing = []
    for display, benchmark, app, workload in WORKLOADS:
        std = anon_kb(results, benchmark, app, workload, "std")
        bpf = anon_kb(results, benchmark, app, workload, "bpf")
        if std is None or bpf is None:
            what = f"{app or 'chrome'} '{workload}' memory data"
            print(f"warning: no {what}", file=sys.stderr)
            missing.append(what)
            continue
        data.append((display, std, bpf))
    return data, missing


def main():
    parser = argparse.ArgumentParser(
        description="Plot steady-state dirty memory reduction")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)
    data, missing = collect_data(results)
    if missing:
        print(f"error: {len(missing)} workload(s) missing from results; "
              f"the figure would be incomplete", file=sys.stderr)
        sys.exit(1)

    labels = [d[0] for d in data]
    pct_reduction = [(1 - d[2] / d[1]) * 100 if d[1] > 0 else 0 for d in data]

    # Print summary
    print(f"\n  {'Workload':<20s} {'Std (kB)':>10s} {'BPF (kB)':>10s} {'Reduction':>10s}",
          file=sys.stderr)
    print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10}", file=sys.stderr)
    for (lbl, std, bpf), pct in zip(data, pct_reduction):
        print(f"  {lbl.replace(chr(10),' '):<20s} {std:>10d} {bpf:>10d} {pct:>9.1f}%",
              file=sys.stderr)
    print(file=sys.stderr)

    color = "forestgreen"
    x = np.arange(len(labels))
    width = 0.5

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(x, pct_reduction, width, color=color)

    for bar, pct in zip(bars, pct_reduction):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{pct:.0f}%", ha="center", va="bottom", fontsize=16,
                fontweight="bold", color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=14)
    ax.tick_params(axis="y", labelsize=18)
    ax.set_ylabel("Dirty memory reduction (%)", fontsize=18)
    ax.set_ylim(0, max(pct_reduction) * 1.25)
    ax.grid(False)

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    fig.savefig(args.output, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
