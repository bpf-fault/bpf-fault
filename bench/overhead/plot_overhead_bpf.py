#!/usr/bin/env python3
# Plot bpf_fault overhead as a single-lane timeline.
#
# Usage:
#   ./plot_overhead_bpf.py                                       # defaults
#   ./plot_overhead_bpf.py -i ../../results/overhead_bpf.csv        # custom input
#   ./plot_overhead_bpf.py -o ../../figures/overhead_bpf.pdf        # custom output

import argparse
import csv
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Patch

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../../results/overhead_bpf.csv")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../../figures/overhead_bpf.pdf")


def load_overhead_csv(path):
    """Load overhead CSV and return column-wise averages across runs."""
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    averages = {}
    for key in rows[0]:
        averages[key] = np.mean([float(r[key]) for r in rows])
    return averages


# ---------------------------------------------------------------------------
#  Category → color mapping
# ---------------------------------------------------------------------------
CAT_COLORS = {
    "fault":    "#5b6abf",  # muted indigo — #PF entry/exit (unavoidable)
    "bpf":      "#e74c3c",  # red — alloc + BPF program (the main cost)
    "lock":     "#e67e22",  # orange — VMA lock + page table walk
    "page":     "#27ae60",  # emerald — PTE installation
}


def build_timeline(avgs):
    """Return a list of (label, duration_ns, category) tuples."""
    phases = [
        ("Fault\ndispatch",     avgs["fault_dispatch_avg_ns"],    "fault"),
        ("Alloc +\nBPF prog",   avgs["alloc_bpf_prog_avg_ns"],   "bpf"),
        ("VMA lock\n+ pgtable", avgs["vma_lock_pgtable_avg_ns"], "lock"),
        ("PTE\ninstall",        avgs["pte_install_avg_ns"],       "page"),
        ("#PF\nexit",           avgs["kernel_to_user_avg_ns"],    "fault"),
    ]
    return phases


def plot_timeline(avgs, output):
    phases = build_timeline(avgs)

    total = sum(p[1] for p in phases)

    fig, ax = plt.subplots(figsize=(11, 2.4))

    lane_y = 0.0
    bar_h = 0.6

    # Draw phases
    left = 0
    rects = []
    for label, dur, cat in phases:
        color = CAT_COLORS[cat]
        ax.barh(
            lane_y, dur, left=left, height=bar_h,
            color=color, edgecolor="white",
            linewidth=0.6,
        )
        rects.append((label, dur, cat, left))
        left += dur

    # Label segments
    for label, dur, cat, left in rects:
        cx = left + dur / 2
        pct = dur / total * 100
        if pct < 2:
            continue
        fontsize = 9.5 if pct >= 5 else 7.5
        ax.text(
            cx, lane_y, label,
            ha="center", va="center",
            fontsize=fontsize, color="white", weight="bold",
            linespacing=0.85,
        )

    # Lane label
    ax.text(-total * 0.01, lane_y, "Faulting\nThread",
            ha="right", va="center", fontsize=12, weight="bold")

    # --- Legend ---
    cat_ns = {}
    for label, dur, cat in phases:
        cat_ns[cat] = cat_ns.get(cat, 0) + dur
    cat_total = sum(cat_ns.values())

    def pct(cat):
        return 100.0 * cat_ns.get(cat, 0) / cat_total if cat_total else 0

    legend_items = [
        Patch(facecolor=CAT_COLORS["fault"], label=f"#PF paths ({pct('fault'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["bpf"],   label=f"Alloc + BPF prog ({pct('bpf'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["lock"],  label=f"VMA lock + pgtable ({pct('lock'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["page"],  label=f"PTE install ({pct('page'):.0f}%)"),
    ]

    # --- Axes ---
    ax.set_xlim(-total * 0.10, total * 1.02)
    ax.set_ylim(-0.55, 0.85)
    ax.set_yticks([])

    us_ticks = np.arange(0, total / 1000 + 0.5, 0.5)
    ax.set_xticks(us_ticks * 1000)
    ax.set_xticklabels([f"{v:.1f}" for v in us_ticks])
    ax.set_xlabel("Time (\u00b5s)", fontsize=16)
    ax.tick_params(axis="x", labelsize=16)

    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    ax.legend(
        handles=legend_items, loc="upper center",
        bbox_to_anchor=(0.5, 1.35), ncol=4, fontsize=11,
        frameon=False, handlelength=1.2, handletextpad=0.4,
        columnspacing=1.0,
    )

    fig.tight_layout()
    fig.savefig(output, metadata={"creationDate": None}, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Plot bpf_fault overhead breakdown timeline")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input CSV results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    avgs = load_overhead_csv(args.input)
    phases = build_timeline(avgs)

    print("bpf_fault phases:", file=sys.stderr)
    t = 0
    for label, dur, cat in phases:
        flat = label.replace("\n", " ")
        print(f"  [{t:6.0f} → {t+dur:6.0f}]  {dur:5.0f} ns  {flat:20s}  ({cat})",
              file=sys.stderr)
        t += dur

    print(f"\nTotal latency: {sum(p[1] for p in phases):.0f} ns",
          file=sys.stderr)

    plot_timeline(avgs, args.output)
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
