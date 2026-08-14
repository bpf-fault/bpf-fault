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

# (display_label, json_filename) per VMM. Labels stay unprefixed when a
# single VMM is plotted (the existing Figure 9); --vmm both prefixes
# them so the eight groups are distinguishable.
_FC_WORKLOAD_MAP = [
    ("Redis", "snapshot_benchmark_redis_heavy.json"),
    ("Memcached", "snapshot_benchmark_memcached_heavy.json"),
]
_QEMU_WORKLOAD_MAP = [
    ("Redis", "snapshot_benchmark_qemu_redis_heavy.json"),
    ("Memcached", "snapshot_benchmark_qemu_memcached_heavy.json"),
]


def _workload_map(vmm):
    if vmm == "fc":
        return _FC_WORKLOAD_MAP
    if vmm == "qemu":
        return _QEMU_WORKLOAD_MAP
    return (
        [(f"FC {wl}", f) for wl, f in _FC_WORKLOAD_MAP]
        + [(f"QEMU {wl}", f) for wl, f in _QEMU_WORKLOAD_MAP]
    )

# --- paper mode ------------------------------------------------------
#
# Element sizes taken verbatim from the Figure 9 PDFs currently in the
# paper (read out of them: 34pt ylabel, 28pt y ticks, 26pt x ticks, 24pt
# legend, on a 12x6in canvas). Specifying every element at the original's
# physical scale means LaTeX scales type and strokes together, so a
# regenerated figure drops into the same \includegraphics width and looks
# identical apart from the data. Do not adjust one of these alone to fix
# how the figure looks after scaling -- change the include width instead.
PAPER_FIGSIZE          = (12, 6)
PAPER_XTICK_FONTSIZE   = 26
PAPER_YTICK_FONTSIZE   = 28
PAPER_LABEL_FONTSIZE   = 34
PAPER_LEGEND_FONTSIZE  = 24

# Axis tops with headroom for the legend. The legend is drawn inside the
# axes, so without this it sits on top of the tallest bar (93.8K ops/s
# and 94.9ms in the current data).
PAPER_YLIM_THR_TOP     = 130_000
PAPER_YLIM_LAT         = (0.5, 1000)

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
               kilo_ticks: bool = False, ylim_top: float = None,
               ylim: tuple = None, paper: bool = False):
    """Two bars (userfaultfd / bpf_fault) per (workload, mem) group.

    value_fn extracts the metric from a run's results dict; values are
    averaged across iterations with stddev error bars.
    """
    x = np.arange(len(groups))
    width = 0.35

    fs_xtick  = PAPER_XTICK_FONTSIZE  if paper else FONTSIZE
    fs_ytick  = PAPER_YTICK_FONTSIZE  if paper else FONTSIZE
    fs_label  = PAPER_LABEL_FONTSIZE  if paper else LABEL_FONTSIZE
    fs_legend = PAPER_LEGEND_FONTSIZE if paper else LEGEND_FONTSIZE

    fig, ax = plt.subplots(figsize=PAPER_FIGSIZE if paper else (8, 4.5))

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
                       fontsize=fs_xtick)
    ax.tick_params(axis="y", labelsize=fs_ytick)
    ax.set_ylabel(ylabel, fontsize=fs_label)
    if log_scale:
        ax.set_yscale("log")
        if ylim:
            ax.set_ylim(*ylim)
    else:
        ax.set_ylim(bottom=0, top=ylim_top)
    if kilo_ticks:
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    ax.legend(fontsize=fs_legend, loc="best")
    ax.grid(False)
    fig.tight_layout()

    _savefig(fig, out_path)


def generate(results_dir: str, out_dir: str, output_throughput: str,
             output_latency: str, fc_mems: list[int], paper: bool = False,
             vmm: str = "fc"):
    """Produce the Figure 9 throughput and latency charts."""
    workload_map = _workload_map(vmm)
    all_runs = load_all_runs(results_dir, workload_map)
    print(f"Loaded {len(all_runs)} runs total")

    groups = [(wl_label, mem)
              for wl_label, _ in workload_map
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
        ylim_top=PAPER_YLIM_THR_TOP if paper else 100_000,
        paper=paper,
    )

    print("\nPlotting latency chart...")
    _plot_bars(
        all_runs, groups,
        value_fn=lambda res: res["freeze_window"]["avg_latency_us"] / 1000.0,
        ylabel="Latency (ms)",
        out_path=os.path.join(out_dir, output_latency),
        log_scale=True,
        ylim=PAPER_YLIM_LAT if paper else None,
        paper=paper,
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
    ap.add_argument("--paper", action="store_true",
                    help="Paper mode: match the element sizes of the "
                         "figures already in the paper")
    ap.add_argument("--vmm", choices=["fc", "qemu", "both"], default="fc",
                    help="Which hypervisor's snapshot results to plot")
    args = ap.parse_args()

    generate(args.results_dir, args.out_dir, args.output_throughput,
             args.output_latency, args.fc_mems, paper=args.paper,
             vmm=args.vmm)
    print("\nDone.")


if __name__ == "__main__":
    main()
