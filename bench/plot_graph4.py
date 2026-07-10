#!/usr/bin/env python3
# Graph 4: combined Firecracker + QEMU snapshot benchmark bar chart.
#
# Outputs:
#   results/graph4_throughput.png  — avg throughput (M ops/s) per config
#   results/graph4_latency.png     — avg latency (µs) per config
#
# X-axis groups (with a gap between workloads):
#   FC 8192 MiB | QEMU 16384 MiB  ||  FC 8192 MiB | QEMU 16384 MiB
#         Redis                              Memcached
#
# 4 bars per group:
#   Baseline    — pooled across all 3 modes (9 samples)
#   Synchronous — full mode (3 samples)
#   Async UFFD  — live mode (3 samples)
#   Async eBPF  — live_bpf mode (3 samples)
#
# Usage (zero-arg from bench/):
#   python3 plot_graph4.py
#
# Optional overrides:
#   python3 plot_graph4.py --fc-mem 4096 --out-dir /tmp/

import argparse
import os
import sys

import numpy as np

# Re-use helpers and constants from the existing FC-only plotting script.
_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BENCH_DIR)
from plot_snapshot_benchmark import (  # noqa: E402
    DEFAULT_COLORS,
    FONTSIZE,
    LABEL_FONTSIZE,
    LEGEND_FONTSIZE,
    MODE_ORDER,
    _OPS_SCALE,
    _OPS_UNIT,
    _savefig,
    agg,
    load_runs,
    mem_label,
    select,
)

import matplotlib.pyplot as plt  # noqa: E402 (matplotlib backend set by plot_snapshot_benchmark import)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_RESULTS_DIR = os.path.join(_BENCH_DIR, "results")

# (display_label, fc_json_filename, qemu_json_filename)
_WORKLOAD_MAP = [
    ("Redis",
     "snapshot_benchmark_redis_heavy.json",
     "qemu_snapshot_benchmark_redis.json"),
    ("Memcached",
     "snapshot_benchmark_memcached_heavy.json",
     "qemu_snapshot_benchmark_memcached.json"),
]

_FC_MEM  = 8192   # MiB — FC memory size shown on the chart
_OUT_DIR = _RESULTS_DIR

# Bar series: (mode_key, display_label, color).
# "baseline" is special-cased to pool across all modes.
_SERIES = [
    ("baseline", "Baseline",    DEFAULT_COLORS[4]),   # mediumpurple
    ("full",     "Synchronous", DEFAULT_COLORS[2]),   # firebrick
    ("live",     "Async UFFD",  DEFAULT_COLORS[0]),   # steelblue
    ("live_bpf", "Async eBPF",  DEFAULT_COLORS[3]),   # forestgreen
]

# Hypervisors shown within each workload section (left → right).
_HYPERVISORS = [
    ("fc",   "FC\n{fc_mem} MiB"),
    ("qemu", "QEMU\n16384 MiB"),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_runs(results_dir: str, workload_map: list,
                  fc_mem, include_qemu: bool = True) -> list[dict]:
    """Load and tag runs from FC and QEMU JSON files.

    Tags each run in-place with:
      config["hypervisor"]     — "fc" or "qemu"
      config["workload_label"] — human-readable label (e.g. "Redis")

    FC runs are filtered to fc_mem (an int or a list of ints); QEMU runs
    are kept as-is.
    """
    fc_mems = fc_mem if isinstance(fc_mem, list) else [fc_mem]
    all_runs: list[dict] = []
    for wl_label, fc_file, qemu_file in workload_map:
        fc_path = os.path.join(results_dir, fc_file)
        if os.path.exists(fc_path):
            for r in load_runs(fc_path):
                if r["config"].get("mem_size_mib") in fc_mems:
                    r["config"]["hypervisor"]     = "fc"
                    r["config"]["workload_label"] = wl_label
                    all_runs.append(r)
        else:
            print(f"  WARNING: FC data not found: {fc_path}", file=sys.stderr)

        if not include_qemu:
            continue
        qemu_path = os.path.join(results_dir, qemu_file)
        if os.path.exists(qemu_path):
            for r in load_runs(qemu_path):
                r["config"]["hypervisor"]     = "qemu"
                r["config"]["workload_label"] = wl_label
                all_runs.append(r)
        else:
            print(f"  WARNING: QEMU data not found: {qemu_path}", file=sys.stderr)

    return all_runs


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def _build_groups(workload_map: list, fc_mems: list,
                  include_qemu: bool, gap: float = 0.6):
    """Group layout: one section per workload, one group per FC memory size
    (plus QEMU if enabled), with an extra gap between workload sections.

    Returns (groups, xs): groups = (hypervisor, mem_size_mib, workload_label,
    x_tick_label) per bar group; xs = x position per group. FC ticks carry
    an "FC" prefix only when QEMU groups are shown.
    """
    prefix = "FC\n" if include_qemu else ""
    groups, xs = [], []
    pos = 0.0
    for wl_label, _, _ in workload_map:
        for m in fc_mems:
            groups.append(("fc", m, wl_label, prefix + mem_label(m)))
            xs.append(pos)
            pos += 1.0
        if include_qemu:
            groups.append(("qemu", None, wl_label, "QEMU\n" + mem_label(16384)))
            xs.append(pos)
            pos += 1.0
        pos += gap
    return groups, xs


def plot_graph4(all_runs: list[dict],
                baseline_fn,
                during_fn,
                ylabel: str,
                scale: float,
                unit: str,
                out_path: str,
                workload_map: list,
                fc_mem: int,
                fc_mems: list = None,
                include_qemu: bool = True):
    """Grouped bar chart: 4 bars per (hypervisor/mem × workload) group."""
    fc_mems = fc_mems or [fc_mem]
    groups, xs = _build_groups(workload_map, fc_mems, include_qemu)
    n_sub = len(fc_mems) + (1 if include_qemu else 0)

    x = np.array(xs)
    n_series = len(_SERIES)
    width = 0.7 / n_series

    fig, ax = plt.subplots(figsize=(12, 6))

    for si, (mode_key, mode_label, color) in enumerate(_SERIES):
        means, stds = [], []
        for hv, mem, wl_label, _ in groups:
            match = dict(hypervisor=hv, workload_label=wl_label)
            if mem is not None:
                match["mem_size_mib"] = mem
            if mode_key == "baseline":
                runs = select(all_runs, **match)
                vals = [baseline_fn(r) / scale for r in runs
                        if _safe_val(baseline_fn, r) > 0]
            else:
                runs = select(all_runs, mode=mode_key, **match)
                vals = [during_fn(r) / scale for r in runs
                        if _safe_val(during_fn, r) > 0]
            mean, std = agg(vals)
            means.append(mean)
            stds.append(std)

        offset = (si - (n_series - 1) / 2) * width
        ax.bar(x + offset, means, width=width, label=mode_label,
               color=color, yerr=stds, capsize=3)

    # Sub-labels: hypervisor + mem per tick
    ax.set_xticks(x)
    ax.set_xticklabels([g[3] for g in groups], fontsize=FONTSIZE - 2)
    ax.tick_params(axis="y", labelsize=FONTSIZE)

    # Section labels: workload name centred over each section
    for i, (wl_label, _, _) in enumerate(workload_map):
        mid = (x[i * n_sub] + x[i * n_sub + n_sub - 1]) / 2
        ax.text(mid, -0.17, wl_label, ha="center", va="top",
                fontsize=LABEL_FONTSIZE, fontweight="bold",
                transform=ax.get_xaxis_transform())

    ax.set_ylabel(f"{ylabel} ({unit})", fontsize=LABEL_FONTSIZE)
    ax.legend(fontsize=LEGEND_FONTSIZE)
    ax.set_ylim(bottom=0)
    ax.set_axisbelow(True)
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_xlim(x[0] - 0.6, x[-1] + 0.6)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18)

    _savefig(fig, out_path)


def _safe_val(fn, run: dict) -> float:
    try:
        v = fn(run)
        return float(v) if v is not None else 0.0
    except (KeyError, TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Plot throughput and latency during snapshot (Figure 9).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--results-dir", default=_RESULTS_DIR,
                    help="Directory containing benchmark JSON files")
    ap.add_argument("--fc-mems", type=int, nargs="+", default=[_FC_MEM],
                    metavar="MiB", help="FC memory sizes to compare")
    ap.add_argument("--out-dir", default=_OUT_DIR,
                    help="Output directory for figures")
    ap.add_argument("--output-throughput", default="graph4_throughput.png",
                    help="Throughput figure filename (relative to --out-dir)")
    ap.add_argument("--output-latency", default="graph4_latency.png",
                    help="Latency figure filename (relative to --out-dir)")
    ap.add_argument("--no-qemu", action="store_true",
                    help="Drop the QEMU comparison groups")
    args = ap.parse_args()
    include_qemu = not args.no_qemu

    all_runs = load_all_runs(args.results_dir, _WORKLOAD_MAP, args.fc_mems,
                             include_qemu=include_qemu)
    if not all_runs:
        print("ERROR: no runs loaded — check JSON files exist in results-dir",
              file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(all_runs)} runs total")

    os.makedirs(args.out_dir, exist_ok=True)

    print("\nPlotting throughput chart...")
    plot_graph4(
        all_runs,
        baseline_fn  = lambda r: r["results"]["throughput"]["baseline_ops_s"],
        during_fn    = lambda r: r["results"]["throughput"]["during_ops_s"],
        ylabel       = "Avg Throughput During Snapshot",
        scale        = _OPS_SCALE,
        unit         = _OPS_UNIT,
        out_path     = os.path.join(args.out_dir, args.output_throughput),
        workload_map = _WORKLOAD_MAP,
        fc_mem       = args.fc_mems[0],
        fc_mems      = args.fc_mems,
        include_qemu = include_qemu,
    )

    print("\nPlotting latency chart...")
    plot_graph4(
        all_runs,
        baseline_fn  = lambda r: r["results"]["latency_us"]["baseline_avg"],
        during_fn    = lambda r: r["results"]["latency_us"]["during_avg"],
        ylabel       = "Avg Latency During Snapshot",
        scale        = 1.0,
        unit         = "µs",
        out_path     = os.path.join(args.out_dir, args.output_latency),
        workload_map = _WORKLOAD_MAP,
        fc_mem       = args.fc_mems[0],
        fc_mems      = args.fc_mems,
        include_qemu = include_qemu,
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
