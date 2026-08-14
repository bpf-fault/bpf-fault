#!/usr/bin/env python3
# Plot Figure 6: Firecracker snapshot downtime (6a) and total snapshot
# time (6b), synchronous vs userfaultfd live, per VM memory size.
#
# Usage:
#   ./plot_fc_snapshot_time.py
#   ./plot_fc_snapshot_time.py -w redis_heavy --out-dir ../figures

import argparse
import os
import sys

_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BENCH_DIR)
from snapshot_lib import _savefig, load_runs, select  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402 (backend set by snapshot_lib)
from matplotlib.ticker import MaxNLocator  # noqa: E402

_RESULTS_DIR = os.path.join(_BENCH_DIR, "../results")
_MEMS = [4096, 8192]

# Wide-and-short panels with large type: rendered at half column width,
# the square originals were needlessly tall and the labels small.
FIGSIZE = (6, 3.6)
LABEL_FONTSIZE = 28
TICK_FONTSIZE = 22
LEGEND_FONTSIZE = 22

# (mode, display label, color)
_SERIES = [("full", "Synchronous", "tab:blue"),
           ("live", "userfaultfd", "tab:orange")]


def _mode_means(runs, key):
    """{mode: [mean over iterations at each mem size, in seconds]}"""
    out = {}
    for mode, _, _ in _SERIES:
        vals = []
        for mem in _MEMS:
            matched = select(runs, mode=mode, mem_size_mib=mem)
            if not matched:
                print(f"error: no records for mode={mode} mem={mem}",
                      file=sys.stderr)
                sys.exit(1)
            vals.append(sum(r["results"][key] for r in matched)
                        / len(matched) / 1000.0)
        out[mode] = vals
    return out


def _plot_bars(data, ylabel, out_path, headroom=1.45, yticks=None):
    x = range(len(_MEMS))
    width = 0.35
    fig, ax = plt.subplots(figsize=FIGSIZE)
    for i, (mode, label, color) in enumerate(_SERIES):
        offset = (i - (len(_SERIES) - 1) / 2) * width
        ax.bar([xi + offset for xi in x], data[mode], width=width,
               label=label, color=color)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{m // 1024} GB" for m in _MEMS],
                       fontsize=TICK_FONTSIZE)
    ax.tick_params(axis="y", labelsize=TICK_FONTSIZE)
    if yticks is not None:
        ax.set_yticks(yticks)
    else:
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel(ylabel, fontsize=LABEL_FONTSIZE)
    # Headroom so the legend clears the tallest bar at this squat aspect.
    ax.set_ylim(0, max(max(v) for v in data.values()) * headroom)
    ax.legend(fontsize=LEGEND_FONTSIZE, loc="upper left")
    fig.tight_layout()
    _savefig(fig, out_path)


def main():
    ap = argparse.ArgumentParser(
        description="Plot Firecracker snapshot downtime/total time "
                    "(Figure 6).")
    ap.add_argument("-r", "--results-dir", default=_RESULTS_DIR)
    ap.add_argument("-w", "--workload", default="redis_heavy")
    ap.add_argument("--out-dir", default=_RESULTS_DIR)
    ap.add_argument("--output-downtime", default="figure6a.pdf")
    ap.add_argument("--output-total", default="figure6b.pdf")
    args = ap.parse_args()

    path = os.path.join(args.results_dir,
                        f"snapshot_benchmark_{args.workload}.json")
    if not os.path.isfile(path):
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(1)
    runs = load_runs(path)

    os.makedirs(args.out_dir, exist_ok=True)
    # The downtime panel's tall bar sits under the legend; extra headroom.
    _plot_bars(_mode_means(runs, "downtime_ms"), "Downtime (s)",
               os.path.join(args.out_dir, args.output_downtime),
               headroom=1.75)
    _plot_bars(_mode_means(runs, "total_snapshot_ms"), "Time (s)",
               os.path.join(args.out_dir, args.output_total),
               yticks=[2, 4, 6, 8])


if __name__ == "__main__":
    main()
