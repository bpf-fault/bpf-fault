#!/usr/bin/env python3
# Plot dynamic linking startup wall time for --version across Chrome,
# Clang, Deno, Docker, Node. Startup dirty memory is printed to stderr.
#
# Usage:
#   ./plot_dynlink_startup.py
#   ./plot_dynlink_startup.py -i ../results/dynlink/dynlink_results.json
#   ./plot_dynlink_startup.py -o ../figures/dynlink_startup.pdf

import argparse
import os
import statistics
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
DEFAULT_OUTPUT_TIME = os.path.join(SCRIPT_DIR,
                                   "../figures/dynlink_startup_time.pdf")

# (display name, timing (app, workload), dirty-memory (benchmark, app,
# workload)). Chrome has no --version memory measurement; its "simple
# HTML" workload (the lightest page) is the dirty proxy. Clang's startup
# timing uses -cc1 --help (pure startup, no compilation).
APPS = [
    ("Chrome", ("chrome", "--version"),
     ("chrome_memory", None, "simple HTML")),
    ("Clang", ("clang", "-cc1 --help"),
     ("app_memory", "clang", "--version")),
    ("Deno", ("deno", "--version"),
     ("app_memory", "deno", "--version")),
    ("Docker", ("docker", "--version"),
     ("app_memory", "docker", "--version")),
    ("Node", ("node", "--version"),
     ("app_memory", "node", "--version")),
]


def wall_ms(results, app, workload, mode):
    """Mean wall time across rounds for one app timing workload."""
    vals = results_select(
        results,
        {"benchmark": "app", "app": app, "workload": workload, "mode": mode},
        lambda r: r["wall_ms"])
    return statistics.mean(vals) if vals else None


def dirty_kb(results, benchmark, app, workload, mode):
    match = {"benchmark": benchmark, "workload": workload, "mode": mode}
    if app is not None:
        match["app"] = app
    vals = results_select(results, match, lambda r: r["anon_kb"])
    return vals[0] if vals else None


def collect_data(results):
    data = {}
    for name, (t_app, t_workload), (m_bench, m_app, m_workload) in APPS:
        entry = {
            "std_wall_ms": wall_ms(results, t_app, t_workload, "std"),
            "bpf_wall_ms": wall_ms(results, t_app, t_workload, "bpf"),
            "std_dirty_kb": dirty_kb(results, m_bench, m_app, m_workload,
                                     "std"),
            "bpf_dirty_kb": dirty_kb(results, m_bench, m_app, m_workload,
                                     "bpf"),
        }
        data[name] = entry
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Plot startup time; print dirty memory to stderr")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output-time", default=DEFAULT_OUTPUT_TIME)
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)
    data = collect_data(results)

    app_names = [name for name, _, _ in APPS]
    incomplete = [a for a in app_names
                  if None in data[a].values()]
    if incomplete:
        print(f"error: missing results for: {', '.join(incomplete)} "
              f"(in {args.input})", file=sys.stderr)
        sys.exit(1)

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
        d = data[app]
        sw, bw = d["std_wall_ms"], d["bpf_wall_ms"]
        sd, bd = d["std_dirty_kb"], d["bpf_dirty_kb"]
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


if __name__ == "__main__":
    main()
