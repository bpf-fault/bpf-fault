#!/usr/bin/env python3
# Plot dynamic linking steady-state dirty memory across workloads for
# tested applications in a single grouped bar chart.
#
# Usage:
#   ./plot_dynlink_steady.py
#   ./plot_dynlink_steady.py -o ../figures/dynlink_steady.pdf

import argparse
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "../results/dynlink")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/dynlink_steady.pdf")


def parse_bench_memory(path, label):
    """Parse bench_run_memory for a label, return (std_dirty_kb, bpf_dirty_kb)."""
    text = open(path).read()
    pattern = rf'Memory: {re.escape(label)}.*?\n\s+Standard.*?Anon:\s+(\d+) kB.*?\n\s+BPF.*?Anon:\s+(\d+) kB'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_chrome_memory(path, label):
    """Parse Chrome steady-state memory for a URL label."""
    text = open(path).read()
    # --- example.com (Std: 9 procs, BPF: 9 procs) ---
    #   Private_Dirty         199860 kB    102148 kB
    pattern = rf'{re.escape(label)} \(Std:.*?\n\s+RSS.*?\n\s+Private_Dirty.*?\n\s+Anonymous\s+(\d+) kB\s+(\d+) kB'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_configure_memory(path):
    """Parse configure probe memory."""
    text = open(path).read()
    m = re.search(r'Memory: clang -c.*?\n\s+Standard.*?Anon:\s+(\d+) kB.*?\n\s+BPF.*?Anon:\s+(\d+) kB',
                  text, re.DOTALL)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def collect_data():
    """Return (data, missing): (display_label, std_kb, bpf_kb) tuples and
    a list of what could not be parsed."""
    data = []
    unparsed = []

    clang_path = os.path.join(RESULTS_DIR, "clang_workloads.txt")
    deno_path = os.path.join(RESULTS_DIR, "deno_workloads.txt")
    chrome_path = os.path.join(RESULTS_DIR, "chrome_workloads.txt")
    configure_path = os.path.join(RESULTS_DIR, "configure_ffmpeg.txt")

    def missing(what):
        print(f"warning: {what}", file=sys.stderr)
        unparsed.append(what)

    if os.path.isfile(clang_path):
        for label, display in [("clang -O0 -c", "Clang\n-O0 -c"),
                                ("clang -O2 -o", "Clang\n-O2 -o")]:
            std, bpf = parse_bench_memory(clang_path, label)
            if std is not None:
                data.append((display, std, bpf))
            else:
                missing(f"no '{label}' memory data in {clang_path}")
    else:
        missing(f"{clang_path} not found")

    if os.path.isfile(configure_path):
        std, bpf = parse_configure_memory(configure_path)
        if std is not None:
            data.append(("Clang\nconfigure", std, bpf))
        else:
            missing(f"no configure probe memory data in {configure_path}")
    else:
        missing(f"{configure_path} not found")

    if os.path.isfile(deno_path):
        for label, display in [("deno eval", "Deno\neval"),
                                ("deno HTTP server", "Deno\nHTTP")]:
            std, bpf = parse_bench_memory(deno_path, label)
            if std is not None:
                data.append((display, std, bpf))
            else:
                missing(f"no '{label}' memory data in {deno_path}")
    else:
        missing(f"{deno_path} not found")

    if os.path.isfile(chrome_path):
        for label, display in [("example.com", "Chrome\nexample.com"),
                                ("local content", "Chrome\nPDF")]:
            std, bpf = parse_chrome_memory(chrome_path, label)
            if std is not None:
                data.append((display, std, bpf))
            else:
                missing(f"no '{label}' memory data in {chrome_path}")
    else:
        missing(f"{chrome_path} not found")

    return data, unparsed


def main():
    parser = argparse.ArgumentParser(
        description="Plot steady-state dirty memory reduction")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data, unparsed = collect_data()
    if unparsed:
        print(f"error: {len(unparsed)} workload(s) missing or unparseable "
              f"(see warnings above); the figure would be incomplete",
              file=sys.stderr)
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
