#!/usr/bin/env python3
# Plot snapshot throughput/latency bar charts (Figure 9): average
# throughput and request latency over the freeze-to-snapshot-completion
# window, userfaultfd vs bpf_fault, per workload and memory size.
#
# X-axis groups:  Redis 4GB | Redis 8GB | Memcached 4GB | Memcached 8GB
# Bars per group: userfaultfd (live), bpf_fault (live_bpf)
#
# Usage (zero-arg from bench/):
#   python3 plot_snapshot_throughput.py
#
# Optional overrides:
#   python3 plot_snapshot_throughput.py --fc-mems 4096 8192

import argparse
import os
import sys

import numpy as np

_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BENCH_DIR)
from snapshot_lib import (  # noqa: E402
    FONTSIZE,
    LABEL_FONTSIZE,
    LEGEND_FONTSIZE,
    _savefig,
    agg,
    load_runs,
    mem_label,
    select,
)

import matplotlib.pyplot as plt  # noqa: E402 (backend set by snapshot_lib import)
from matplotlib.ticker import FuncFormatter  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_RESULTS_DIR = os.path.join(_BENCH_DIR, "../results")
_OUT_DIR = _RESULTS_DIR
_FC_MEMS = [4096, 8192]

# (display_label, fc_json_filename)
_WORKLOAD_MAP = [
    ("Redis", "snapshot_benchmark_redis_heavy.json"),
    ("Memcached", "snapshot_benchmark_memcached_heavy.json"),
]

# Bar series: (mode_key, display_label, color)
_SERIES = [
    ("live",     "userfaultfd", "darkorange"),
    ("live_bpf", "bpf_fault",   "forestgreen"),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_runs(results_dir: str, workload_map: list) -> list[dict]:
    """Load runs from the FC JSON files, tagging each with its workload
    label. Every workload file is required — the figure would silently
    lose a group otherwise."""
    missing = [f for _, f in workload_map
               if not os.path.exists(os.path.join(results_dir, f))]
    if missing:
        print(f"error: missing results: {', '.join(missing)} "
              f"(in {results_dir})", file=sys.stderr)
        sys.exit(1)

    all_runs: list[dict] = []
    for wl_label, fc_file in workload_map:
        for r in load_runs(os.path.join(results_dir, fc_file)):
            r["config"]["workload_label"] = wl_label
            all_runs.append(r)
    return all_runs


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def _plot_bars(all_runs: list[dict], groups: list, value_fn, ylabel: str,
               out_path: str, log_scale: bool = False,
               kilo_ticks: bool = False, ylim_top: float = None):
    """Two bars (userfaultfd / bpf_fault) per (workload, mem) group.

    value_fn extracts the metric from a run's results dict; values are
    averaged across iterations with stddev error bars.
    """
    x = np.arange(len(groups))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5))

    for si, (mode_key, mode_label, color) in enumerate(_SERIES):
        means = []
        for wl_label, mem in groups:
            runs = select(all_runs, mode=mode_key,
                          workload_label=wl_label, mem_size_mib=mem)
            vals = [value_fn(r["results"]) for r in runs]
            vals = [v for v in vals if v > 0]
            if not vals:
                print(f"error: no {mode_key} data for {wl_label} at "
                      f"{mem} MiB in {out_path}", file=sys.stderr)
                sys.exit(1)
            mean, _ = agg(vals)
            means.append(mean)

        offset = (si - (len(_SERIES) - 1) / 2) * width
        ax.bar(x + offset, means, width=width, label=mode_label,
               color=color)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{wl}\n{mem_label(mem)}" for wl, mem in groups],
                       fontsize=FONTSIZE)
    ax.tick_params(axis="y", labelsize=FONTSIZE)
    ax.set_ylabel(ylabel, fontsize=LABEL_FONTSIZE)
    if log_scale:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0, top=ylim_top)
    if kilo_ticks:
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    ax.legend(fontsize=LEGEND_FONTSIZE, loc="best")
    ax.grid(False)
    fig.tight_layout()

    _savefig(fig, out_path)


def generate(results_dir: str, out_dir: str, output_throughput: str,
             output_latency: str, fc_mems: list[int]):
    """Produce the Figure 9 throughput and latency charts."""
    all_runs = load_all_runs(results_dir, _WORKLOAD_MAP)
    print(f"Loaded {len(all_runs)} runs total")

    groups = [(wl_label, mem)
              for wl_label, _ in _WORKLOAD_MAP
              for mem in fc_mems]

    os.makedirs(out_dir, exist_ok=True)

    # Freeze-to-snapshot-completion window stats (phases 2-4), matching
    # the paper's "while the VM runs with snapshot WP active" caption.
    print("\nPlotting throughput chart...")
    _plot_bars(
        all_runs, groups,
        value_fn=lambda res: res["freeze_window"]["throughput_ops_s"],
        ylabel="Throughput (ops/s)",
        out_path=os.path.join(out_dir, output_throughput),
        kilo_ticks=True,
        ylim_top=100_000,
    )

    print("\nPlotting latency chart...")
    _plot_bars(
        all_runs, groups,
        value_fn=lambda res: res["freeze_window"]["avg_latency_us"] / 1000.0,
        ylabel="Latency (ms)",
        out_path=os.path.join(out_dir, output_latency),
        log_scale=True,
    )


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
    ap.add_argument("--fc-mems", type=int, nargs="+", default=_FC_MEMS,
                    metavar="MiB", help="Memory sizes to compare")
    ap.add_argument("--out-dir", default=_OUT_DIR,
                    help="Output directory for figures")
    ap.add_argument("--output-throughput", default="snapshot_throughput.pdf",
                    help="Throughput figure filename (relative to --out-dir)")
    ap.add_argument("--output-latency", default="snapshot_latency.pdf",
                    help="Latency figure filename (relative to --out-dir)")
    args = ap.parse_args()

    generate(args.results_dir, args.out_dir, args.output_throughput,
             args.output_latency, args.fc_mems)
    print("\nDone.")


if __name__ == "__main__":
    main()
