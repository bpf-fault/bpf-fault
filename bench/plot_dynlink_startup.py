#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot dynamic linking startup: wall time and dirty memory for --version
# across Chrome, Clang, Deno, Docker, Node.
#
# Usage:
#   ./plot_dynlink_startup.py
#   ./plot_dynlink_startup.py -o ../figures/dynlink_startup.pdf

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
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results/dynlink")
DEFAULT_OUTPUT_TIME = os.path.join(SCRIPT_DIR, "../figures/dynlink_startup_time.pdf")
DEFAULT_OUTPUT_MEM = os.path.join(SCRIPT_DIR, "../figures/dynlink_startup_mem.pdf")

# App order (by reloc count descending)
APPS = [
    ("Chrome",     "chrome_workloads.txt"),
    ("Clang",      "clang_workloads.txt"),
    ("Deno",       "deno_workloads.txt"),
    ("Docker",     None),  # from summary.csv
    ("Node",       None),  # from summary.csv
]

# Hardcoded Docker/Node from summary.csv (--version workloads)
FALLBACK_DATA = {
    "Docker": {
        "std_wall_ms": 15.12, "bpf_wall_ms": 18.30,
        "std_dirty_kb": 2976, "bpf_dirty_kb": 108,
    },
    "Node": {
        "std_wall_ms": 19.76, "bpf_wall_ms": 19.20,
        "std_dirty_kb": 2208, "bpf_dirty_kb": 1540,
    },
}


def parse_chrome_startup(path):
    text = open(path).read()
    # chrome --version                        35        21   -40.0%
    m = re.search(r'chrome --version\s+(\d+)\s+(\d+)', text)
    std_ms = float(m.group(1))
    bpf_ms = float(m.group(2))

    # Memory from first workload block (simple HTML) — use --version if available
    # Actually Chrome doesn't have a --version smaps. Use the summary for dirty.
    # Parse the simple HTML memory as proxy for per-process dirty.
    std_dirty = bpf_dirty = None
    # Look for the per-process breakdown browser line
    lines = text.splitlines()
    browser_std = browser_bpf = None
    in_std = in_bpf = False
    for line in lines:
        if "Standard (" in line:
            in_std = True; in_bpf = False; continue
        if "BPF (" in line:
            in_bpf = True; in_std = False; continue
        if in_std and "browser" in line:
            m2 = re.search(r'(\d+) kB', line)
            if m2:
                browser_std = int(m2.group(1))
            in_std = False
        if in_bpf and "browser" in line:
            m2 = re.search(r'(\d+) kB', line)
            if m2:
                browser_bpf = int(m2.group(1))
            in_bpf = False

    # Use total Anonymous from the first memory section (simple HTML)
    m_anon = re.search(r'Anonymous\s+(\d+) kB\s+(\d+) kB', text)
    if m_anon:
        std_dirty = int(m_anon.group(1))
        bpf_dirty = int(m_anon.group(2))

    return std_ms, bpf_ms, std_dirty, bpf_dirty


def parse_bench_timing(path, pattern):
    """Parse a bench_run style timing line."""
    text = open(path).read()
    # --- deno --version (startup only) ---
    #   Standard: 8.64ms/iter
    #   BPF:      5.98ms/iter
    m = re.search(pattern + r'.*?\n\s+Standard:\s+([\d.]+)ms/iter\n\s+BPF:\s+([\d.]+)ms/iter',
                  text, re.DOTALL)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def parse_bench_memory(path, label):
    """Parse bench_run_memory output for a given label."""
    text = open(path).read()
    # --- Memory: clang --version ---
    #   Standard   RSS: 37360 kB  Priv_Dirty:  9272 kB ...
    #   BPF        RSS: 31348 kB  Priv_Dirty:  3256 kB ...
    pattern = rf'Memory: {re.escape(label)}.*?\n\s+Standard.*?Anon:\s+(\d+) kB.*?\n\s+BPF.*?Anon:\s+(\d+) kB'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def collect_data():
    data = {}

    # Chrome
    chrome_path = os.path.join(RESULTS_DIR, "chrome_workloads.txt")
    if os.path.isfile(chrome_path):
        std_ms, bpf_ms, std_dirty, bpf_dirty = parse_chrome_startup(chrome_path)
        data["Chrome"] = {
            "std_wall_ms": std_ms, "bpf_wall_ms": bpf_ms,
            "std_dirty_kb": std_dirty, "bpf_dirty_kb": bpf_dirty,
        }

    # Clang
    clang_path = os.path.join(RESULTS_DIR, "clang_workloads.txt")
    if os.path.isfile(clang_path):
        std_ms, bpf_ms = parse_bench_timing(clang_path, r'-cc1 --help')
        std_dirty, bpf_dirty = parse_bench_memory(clang_path, "clang --version")
        data["Clang"] = {
            "std_wall_ms": std_ms, "bpf_wall_ms": bpf_ms,
            "std_dirty_kb": std_dirty, "bpf_dirty_kb": bpf_dirty,
        }

    # Deno
    deno_path = os.path.join(RESULTS_DIR, "deno_workloads.txt")
    if os.path.isfile(deno_path):
        std_ms, bpf_ms = parse_bench_timing(deno_path, r'--version')
        std_dirty, bpf_dirty = parse_bench_memory(deno_path, "deno --version")
        data["Deno"] = {
            "std_wall_ms": std_ms, "bpf_wall_ms": bpf_ms,
            "std_dirty_kb": std_dirty, "bpf_dirty_kb": bpf_dirty,
        }

    # Docker and Node from summary.csv
    for app in ["Docker", "Node"]:
        data[app] = FALLBACK_DATA[app]

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Plot startup time and dirty memory")
    parser.add_argument("-o", "--output-time", default=DEFAULT_OUTPUT_TIME)
    parser.add_argument("-m", "--output-mem", default=DEFAULT_OUTPUT_MEM)
    args = parser.parse_args()

    data = collect_data()

    app_names = ["Chrome", "Clang", "Deno", "Docker", "Node"]
    app_labels = {
        "Chrome": "Chrome\n(1.04M)",
        "Clang":  "Clang\n(512K)",
        "Deno":   "Deno\n(182K)",
        "Docker": "Docker\n(120K)",
        "Node":   "Node\n(56K)",
    }

    # Print summary
    print(f"\n  {'App':<10s} {'Std (ms)':>10s} {'BPF (ms)':>10s} {'Wall %':>8s}"
          f"  {'Std Dirty':>10s} {'BPF Dirty':>10s} {'Dirty %':>8s}",
          file=sys.stderr)
    print(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*8}"
          f"  {'─'*10} {'─'*10} {'─'*8}", file=sys.stderr)
    for app in app_names:
        d = data.get(app, {})
        sw = d.get("std_wall_ms", 0)
        bw = d.get("bpf_wall_ms", 0)
        sd = d.get("std_dirty_kb", 0)
        bd = d.get("bpf_dirty_kb", 0)
        wp = (bw - sw) / sw * 100 if sw else 0
        dp = (bd - sd) / sd * 100 if sd else 0
        print(f"  {app:<10s} {sw:>10.1f} {bw:>10.1f} {wp:>+7.1f}%"
              f"  {sd:>8d} kB {bd:>8d} kB {dp:>+7.1f}%", file=sys.stderr)
    print(file=sys.stderr)

    x = np.arange(len(app_names))
    width = 0.35
    colors_std = "steelblue"
    colors_bpf = "forestgreen"
    xlabels = [app_labels[a] for a in app_names]

    # (a) Wall time — separate file
    fig, ax = plt.subplots(figsize=(8, 4.5))
    std_wall = [data[a]["std_wall_ms"] for a in app_names]
    bpf_wall = [data[a]["bpf_wall_ms"] for a in app_names]
    ax.bar(x - width/2, std_wall, width, label="Baseline", color=colors_std)
    ax.bar(x + width/2, bpf_wall, width, label="bpf_fault", color=colors_bpf)
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontsize=18)
    ax.tick_params(axis="y", labelsize=18)
    ax.set_ylabel("Startup time (ms)", fontsize=26)
    ax.legend(fontsize=20, loc="best")
    ax.set_axisbelow(True)
    ax.grid(False)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(args.output_time)), exist_ok=True)
    fig.savefig(args.output_time, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    print(f"Plot saved to {args.output_time}", file=sys.stderr)

    # (b) Dirty memory reduction (%) — separate file
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pct_reduction = [
        (1 - data[a]["bpf_dirty_kb"] / data[a]["std_dirty_kb"]) * 100
        if data[a]["std_dirty_kb"] > 0 else 0
        for a in app_names
    ]
    bars = ax.bar(x, pct_reduction, width * 1.5, color=colors_bpf)
    # Add value labels on bars
    for i, (bar, pct) in enumerate(zip(bars, pct_reduction)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{pct:.0f}%", ha="center", va="bottom", fontsize=16,
                fontweight="bold", color=colors_bpf)
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontsize=18)
    ax.tick_params(axis="y", labelsize=18)
    ax.set_ylabel("Dirty memory reduction (%)", fontsize=18)
    ax.set_ylim(0, 110)
    ax.set_axisbelow(True)
    ax.grid(False)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(args.output_mem)), exist_ok=True)
    fig.savefig(args.output_mem, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    print(f"Plot saved to {args.output_mem}", file=sys.stderr)


if __name__ == "__main__":
    main()
