#!/usr/bin/env python3
"""Graphs 1 & 2: Downtime and Total Snapshot Time — Full vs. Live (UFFD).

Outputs:
  results/graph1_downtime.png    — VM downtime (ms) per configuration
  results/graph2_total_time.png  — Total snapshot time (ms) per configuration

X-axis groups (with a gap before QEMU):
  FC 2048 MiB  FC 4096 MiB  FC 8192 MiB  |  QEMU 16384 MiB

2 bars per group:
  Synchronous — full mode (3 iterations)
  Live (UFFD) — live mode (3 iterations)

Usage (zero-arg from bench/):
    python3 plot_graphs12.py

Optional overrides:
    python3 plot_graphs12.py --out-dir /tmp/
"""

import argparse
import os
import sys

import numpy as np

_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BENCH_DIR)
from plot_snapshot_benchmark import (  # noqa: E402
    DEFAULT_COLORS,
    FONTSIZE,
    LABEL_FONTSIZE,
    LEGEND_FONTSIZE,
    _savefig,
    agg,
    load_runs,
    select,
)

import matplotlib.pyplot as plt  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_RESULTS_DIR = os.path.join(_BENCH_DIR, "results")
_FC_JSON     = "snapshot_benchmark_redis_heavy.json"
_QEMU_JSON   = "qemu_snapshot_benchmark_redis.json"
_OUT_DIR     = _RESULTS_DIR

# Bar series: (mode_key, display_label, color)
_SERIES = [
    ("full", "Synchronous", DEFAULT_COLORS[2]),   # firebrick
    ("live", "Live (UFFD)", DEFAULT_COLORS[0]),   # steelblue
]

# X-axis groups: (hypervisor_tag, mem_size_mib, x_tick_label)
_GROUPS = [
    ("fc",   2048,  "FC\n2048 MiB"),
    ("fc",   4096,  "FC\n4096 MiB"),
    ("fc",   8192,  "FC\n8192 MiB"),
    ("qemu", 16384, "QEMU\n16384 MiB"),
]

# X positions — 0,1,2 for FC groups, then a 0.5-wide gap before QEMU.
_X = [0.0, 1.0, 2.0, 3.5]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tagged(json_path: str, hypervisor: str) -> list[dict]:
    """Load runs from a JSON file and tag each with config['hypervisor']."""
    runs = load_runs(json_path)
    for r in runs:
        r["config"]["hypervisor"] = hypervisor
    return runs


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def plot_bar(all_runs: list[dict],
             metric_key: str,
             ylabel: str,
             out_path: str):
    """Grouped bar chart for a single results field (e.g. 'downtime_ms')."""
    x = np.array(_X)
    n_series = len(_SERIES)
    width = 0.7 / n_series

    fig, ax = plt.subplots(figsize=(11, 6))

    for si, (mode_key, mode_label, color) in enumerate(_SERIES):
        means, stds = [], []
        for hv, mem, _ in _GROUPS:
            runs = select(all_runs, hypervisor=hv, mem_size_mib=mem, mode=mode_key)
            vals = [r["results"][metric_key] for r in runs
                    if r["results"].get(metric_key) is not None]
            mean, std = agg(vals)
            means.append(mean)
            stds.append(std)

        offset = (si - (n_series - 1) / 2) * width
        ax.bar(x + offset, means, width=width, label=mode_label,
               color=color, yerr=stds, capsize=3)

    ax.set_xticks(x)
    ax.set_xticklabels([g[2] for g in _GROUPS], fontsize=FONTSIZE - 1)
    ax.tick_params(axis="y", labelsize=FONTSIZE)
    ax.set_ylabel(ylabel, fontsize=LABEL_FONTSIZE)
    ax.legend(fontsize=LEGEND_FONTSIZE)
    ax.set_ylim(bottom=0)
    ax.set_axisbelow(True)
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_xlim(x[0] - 0.6, x[-1] + 0.6)
    fig.tight_layout()

    _savefig(fig, out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(results_dir: str = _RESULTS_DIR, out_dir: str = _OUT_DIR):
    fc_path   = os.path.join(results_dir, _FC_JSON)
    qemu_path = os.path.join(results_dir, _QEMU_JSON)

    all_runs = []
    for path, hv in ((fc_path, "fc"), (qemu_path, "qemu")):
        if os.path.exists(path):
            all_runs.extend(load_tagged(path, hv))
        else:
            print(f"  WARNING: not found: {path}", file=sys.stderr)

    if not all_runs:
        print("ERROR: no runs loaded", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(all_runs)} runs total")

    os.makedirs(out_dir, exist_ok=True)

    print("\nPlotting graph1 (downtime)...")
    plot_bar(
        all_runs,
        metric_key = "downtime_ms",
        ylabel     = "Downtime (ms)",
        out_path   = os.path.join(out_dir, "graph1_downtime.png"),
    )

    print("\nPlotting graph2 (total snapshot time)...")
    plot_bar(
        all_runs,
        metric_key = "total_snapshot_ms",
        ylabel     = "Total Snapshot Time (ms)",
        out_path   = os.path.join(out_dir, "graph2_total_time.png"),
    )

    print("\nDone.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Plot graphs 1 & 2: downtime and total snapshot time.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--results-dir", default=_RESULTS_DIR,
                    help="Directory containing benchmark JSON files")
    ap.add_argument("--out-dir", default=_OUT_DIR,
                    help="Output directory for PNG files")
    args = ap.parse_args()
    main(results_dir=args.results_dir, out_dir=args.out_dir)
