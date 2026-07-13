#!/usr/bin/env python3
# Plot baseline anonymous fault overhead as a single-lane timeline.
# Supports both read-fault (zero-page) and write-fault (page alloc) modes.
#
# Usage:
#   ./plot_overhead_baseline.py                                       # defaults
#   ./plot_overhead_baseline.py -i ../../results/overhead_baseline.csv   # custom input
#   ./plot_overhead_baseline.py -o ../../figures/overhead_baseline.pdf   # custom output

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
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../../results/overhead_baseline.csv")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../../figures/overhead_baseline.pdf")


def load_overhead_csv(path):
    """Load overhead CSV and return column-wise averages across runs."""
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    averages = {}
    for key in rows[0]:
        try:
            averages[key] = np.mean([float(r[key]) for r in rows])
        except ValueError:
            averages[key] = rows[0][key]  # string column (fault_mode)
    return averages


# ---------------------------------------------------------------------------
#  Category → color mapping (per-mode)
# ---------------------------------------------------------------------------
CAT_COLORS = {
    "fault":     "#5b6abf",  # muted indigo — #PF entry/exit
    "pgtable":   "#8e44ad",  # purple — page table walk
    "zeropage":  "#27ae60",  # emerald — zero-page map (read mode)
    "pagealloc": "#e74c3c",  # red — page alloc + PTE (write mode)
}


def detect_mode(avgs):
    """Detect read vs write mode from CSV columns."""
    if "fault_mode" in avgs:
        return "write" if avgs["fault_mode"] == "write" else "read"
    if "page_alloc_pte_avg_ns" in avgs:
        return "write"
    return "read"


def build_timeline(avgs, mode):
    """Return a list of (label, duration_ns, category) tuples."""
    if mode == "write":
        phase3_key = "page_alloc_pte_avg_ns"
        phase3_label = "Page alloc\n+ PTE"
        phase3_cat = "pagealloc"
    else:
        phase3_key = "zero_page_map_avg_ns"
        phase3_label = "Zero-page\nmap"
        phase3_cat = "zeropage"

    phases = [
        ("#PF\nenter",        avgs["fault_entry_avg_ns"],      "fault"),
        ("Page table\nwalk",  avgs["page_table_walk_avg_ns"],  "pgtable"),
        (phase3_label,        avgs[phase3_key],                phase3_cat),
        ("#PF\nexit",         avgs["kernel_to_user_avg_ns"],   "fault"),
    ]
    return phases


def plot_timeline(avgs, mode, output):
    phases = build_timeline(avgs, mode)

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
        Patch(facecolor=CAT_COLORS["fault"],   label=f"#PF paths ({pct('fault'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["pgtable"], label=f"Page table walk ({pct('pgtable'):.0f}%)"),
    ]
    if mode == "write":
        legend_items.append(
            Patch(facecolor=CAT_COLORS["pagealloc"],
                  label=f"Page alloc + PTE ({pct('pagealloc'):.0f}%)"))
    else:
        legend_items.append(
            Patch(facecolor=CAT_COLORS["zeropage"],
                  label=f"Zero-page map ({pct('zeropage'):.0f}%)"))

    # --- Axes ---
    ax.set_xlim(-total * 0.10, total * 1.02)
    ax.set_ylim(-0.55, 0.85)
    ax.set_yticks([])

    # Adaptive tick spacing
    total_us = total / 1000
    if total_us < 1.5:
        step = 0.25
        fmt = "{:.2f}"
    elif total_us < 4:
        step = 0.5
        fmt = "{:.1f}"
    else:
        step = 1.0
        fmt = "{:.0f}"

    us_ticks = np.arange(0, total_us + step, step)
    ax.set_xticks(us_ticks * 1000)
    ax.set_xticklabels([fmt.format(v) for v in us_ticks])
    ax.set_xlabel("Time (\u00b5s)", fontsize=16)
    ax.tick_params(axis="x", labelsize=16)

    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    ax.legend(
        handles=legend_items, loc="upper center",
        bbox_to_anchor=(0.5, 1.35), ncol=len(legend_items), fontsize=11,
        frameon=False, handlelength=1.2, handletextpad=0.4,
        columnspacing=1.0,
    )

    fig.tight_layout()
    fig.savefig(output, metadata={"creationDate": None}, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Plot baseline anonymous fault overhead breakdown")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input CSV results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    parser.add_argument("-m", "--mode", choices=["read", "write"],
                        default=None,
                        help="Fault mode (auto-detected from CSV if omitted)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    avgs = load_overhead_csv(args.input)
    mode = args.mode or detect_mode(avgs)
    phases = build_timeline(avgs, mode)

    print(f"Baseline phases ({mode} faults):", file=sys.stderr)
    t = 0
    for label, dur, cat in phases:
        flat = label.replace("\n", " ")
        print(f"  [{t:6.0f} → {t+dur:6.0f}]  {dur:5.0f} ns  {flat:20s}  ({cat})",
              file=sys.stderr)
        t += dur

    print(f"\nTotal latency: {sum(p[1] for p in phases):.0f} ns",
          file=sys.stderr)

    plot_timeline(avgs, mode, args.output)
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
