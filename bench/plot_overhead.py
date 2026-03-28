#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Plot userfaultfd overhead as a two-lane (faulting thread / handler thread)
# timeline with IPI arrows between them.
#
# Usage:
#   ./plot_overhead.py                                          # defaults
#   ./plot_overhead.py -i ../results/overhead.csv               # custom input
#   ./plot_overhead.py -o ../figures/overhead_breakdown.pdf     # custom output

import argparse
import csv
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrowPatch, PathPatch
from matplotlib.path import Path

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/overhead.csv")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/overhead_breakdown.pdf")


def load_overhead_csv(path):
    """Load overhead.csv and return column-wise averages across runs."""
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    averages = {}
    for key in rows[0]:
        averages[key] = np.mean([float(r[key]) for r in rows])
    return averages


# ---------------------------------------------------------------------------
#  Category → color mapping (same 5 categories as the analysis)
# ---------------------------------------------------------------------------
CAT_COLORS = {
    "fault":    "#5b6abf",  # muted indigo — #PF path (unavoidable)
    "sched":    "#c0392b",  # red — scheduling + IPI (optimizable)
    "syscall":  "#e67e22",  # orange — syscall crossings (optimizable)
    "plumbing": "#f1c40f",  # yellow — uffd protocol (optimizable)
    "page":     "#27ae60",  # emerald — page setup (unavoidable)
    "user":     "#95a5a6",  # grey — userspace
    "idle":     "#ecf0f1",  # very light grey — idle / sleeping
}


def build_timeline(avgs):
    """Return (faulter_phases, handler_phases) as lists of
    (label, duration_ns, category) tuples, laid out on the critical path.

    The critical path is 14.6 µs from fault to resume.  Each phase is
    assigned to the CPU it runs on.  Phases on the other CPU during that
    time window are shown as idle/sleeping.

    Timeline from the overhead-analysis.txt:

    Faulter CPU                          Handler CPU
    ───────────                          ───────────
    1a.  Kernel fault path  (906)        (idle)
    1b1. Message enqueue    (932)        (idle)
    1b2. Wake + schedule   (1865)        (idle — IPI in flight)
           ─── IPI #1 ──────────────►
    (sleeping)                           1b3. Ctx switch       (1097)
    (sleeping)                           1b4. Poll return      (1072)
    (sleeping)                           2a.  read() entry       (xxx)
    (sleeping)                           2b.  uffd read          (xxx)
    (sleeping)                           2c.  read() exit        (xxx)
    (sleeping)                           3.   User processing    (28)
    (sleeping)                           4a1. ioctl entry       (630)
    (sleeping)                           4a2. Page alloc+copy  (1300)
    (sleeping)                           4a3. PTE install      (1003)
    (sleeping)                           5a1. Wake processing   (373)
           ◄─── IPI #2 ────────────
    5a2. IPI + scheduling  (2973)        4b.  ioctl return      (928)
    5a3. Post-wake cleanup  (638)        (idle)
    5b.  Fault return      (1194)        (idle)
    """

    # Phase definitions: (label, csv_key, category)
    # Faulter CPU active phases
    f_1a  = ("#PF\nenter",             avgs["kernel_fault_path_avg_ns"],   "fault")
    f_1b1 = ("Queue\nmsg",            avgs["huf_enqueue_avg_ns"],         "plumbing")
    f_1b2 = ("Wake +\nschedule",     avgs["wakeup_poll_to_sched_avg_ns"],"sched")
    f_5a2 = ("IPI +\nscheduling",    avgs["ipi_schedule_avg_ns"],        "sched")
    f_5a3 = ("Post-wake\ncleanup",   avgs["huf_cleanup_avg_ns"],         "plumbing")
    f_5b  = ("#PF\nexit",             avgs["kernel_to_user_avg_ns"],      "fault")

    # Handler CPU active phases
    h_1b3 = ("Ctx\nswitch",      avgs["ctx_switch_to_handler_avg_ns"], "sched")
    h_1b4 = ("poll()\nreturn",        avgs["handler_poll_return_avg_ns"],   "syscall")
    h_2a  = ("read()\nentry",        avgs["read_entry_avg_ns"],            "syscall")
    h_2b  = ("uffd\nread",          avgs["read_work_avg_ns"],             "plumbing")
    h_2c  = ("read()\nexit",        avgs["read_exit_avg_ns"],             "syscall")
    h_3   = ("User\nproc",           avgs["user_processing_avg_ns"],       "user")
    h_4a1 = ("ioctl\nentry",         avgs["ioctl_overhead_avg_ns"],        "syscall")
    h_4a2 = ("Page alloc\n+ copy",   avgs["page_alloc_copy_avg_ns"],      "page")
    h_4a3 = ("PTE\ninstall",         avgs["pte_install_avg_ns"],           "page")
    h_5a1 = ("Wake\nproc",           avgs["wake_processing_avg_ns"],       "plumbing")
    h_4b  = ("ioctl\nreturn",        avgs["wake_ioctl_ret_avg_ns"],        "syscall")

    # --- Faulter lane: sequential phases with idle gaps ---
    faulter_active_start = [f_1a, f_1b1, f_1b2]
    handler_active = [h_1b3, h_1b4, h_2a, h_2b, h_2c, h_3, h_4a1, h_4a2, h_4a3, h_5a1]
    faulter_active_end = [f_5a2, f_5a3, f_5b]

    # Compute the sleeping gap on faulter = sum of handler phases before IPI #2
    faulter_sleep_dur = sum(p[1] for p in handler_active)

    # Handler idle at start = sum of first 3 faulter phases
    handler_idle_start = sum(p[1] for p in faulter_active_start)

    # Handler's 4b overlaps with faulter's 5a2.  Show it starting at the
    # same time as 5a2 on the handler lane.
    faulter_end_dur = sum(p[1] for p in faulter_active_end)
    handler_idle_end = faulter_end_dur - h_4b[1]

    # Build the lane lists: (label, duration, category)
    faulter_phases = (
        list(faulter_active_start)
        + [("sleeping", faulter_sleep_dur, "idle")]
        + list(faulter_active_end)
    )

    handler_phases = (
        [("idle", handler_idle_start, "idle")]
        + list(handler_active)
        + [h_4b]
        + [("idle", max(0, handler_idle_end), "idle")]
    )

    return faulter_phases, handler_phases


def plot_timeline(avgs, output):
    faulter_phases, handler_phases = build_timeline(avgs)

    total = sum(p[1] for p in faulter_phases)

    fig, ax = plt.subplots(figsize=(11, 3.5))

    lane_y = {"handler": 1.0, "faulter": 0.0}
    bar_h = 0.6

    def draw_lane(phases, y):
        """Draw a sequence of colored boxes for one CPU lane."""
        left = 0
        rects = []
        for label, dur, cat in phases:
            color = CAT_COLORS[cat]
            edgecolor = "#bdc3c7" if cat == "idle" else "white"
            linestyle = ":" if cat == "idle" else "-"
            ax.barh(
                y, dur, left=left, height=bar_h,
                color=color, edgecolor=edgecolor,
                linewidth=0.6, linestyle=linestyle,
            )
            rects.append((label, dur, cat, left))
            left += dur
        return rects

    f_rects = draw_lane(faulter_phases, lane_y["faulter"])
    h_rects = draw_lane(handler_phases, lane_y["handler"])

    # --- Label the active (non-idle) segments ---
    def label_rects(rects, y, skip_labels=None):
        if skip_labels is None:
            skip_labels = set()
        for label, dur, cat, left in rects:
            if label in skip_labels:
                continue
            if cat == "idle":
                # Label sleeping/idle with italic
                cx = left + dur / 2
                pct = dur / total * 100
                if pct > 5:
                    ax.text(
                        cx, y, "sleeping" if dur > 2000 else "",
                        ha="center", va="center",
                        fontsize=11, color="#7f8c8d", style="italic",
                    )
                continue
            cx = left + dur / 2
            pct = dur / total * 100
            if pct < 1.5:
                continue  # too narrow for a label
            if pct < 5:
                fontsize = 7.5
            # elif pct < 7:
            #     fontsize = 9
            else:
                fontsize = 9.5
            # Per-label overrides
            if label == "Page alloc\n+ copy":
                fontsize = 9.5
            elif label in ("#PF\nenter", "#PF\nexit"):
                fontsize = 9.5
            ax.text(
                cx, y, label,
                ha="center", va="center",
                fontsize=fontsize, color="white", weight="bold",
                linespacing=0.85,
            )

    label_rects(f_rects, lane_y["faulter"],
                skip_labels={"Post-wake\ncleanup", "Queue\nmsg"})
    label_rects(h_rects, lane_y["handler"],
                skip_labels={"read()\nentry", "uffd\nread",
                             "read()\nexit", "ioctl\nentry", "ioctl\nreturn"})

    # --- IPI arrows ---
    # IPI #1: faulter sends IPI near end of "Wake + schedule" → handler "Context switch"
    # Find the x-coordinates
    ipi1_src_x = sum(p[1] for p in faulter_phases[:3])  # end of Wake + schedule
    ipi1_dst_x = sum(p[1] for p in handler_phases[:1])         # start of 1b3 on handler

    # IPI #2: handler sends IPI at end of "Wake proc" → faulter "IPI + scheduling"
    ipi2_src_x = sum(p[1] for p in handler_phases[:11])  # end of 5a1
    ipi2_dst_x = sum(p[1] for p in faulter_phases[:4])  # start of 5a2 on faulter

    faulter_top = lane_y["faulter"] + bar_h / 2
    handler_bot = lane_y["handler"] - bar_h / 2
    mid_y1 = (lane_y["faulter"] + lane_y["handler"]) / 2

    arrow_kw = dict(
        arrowstyle="->,head_width=0.4,head_length=0.25",
        color="#2c3e50", linewidth=1.5,
    )

    # IPI #1: faulter → handler (upward)
    ax.annotate(
        "", xy=(ipi1_dst_x, handler_bot),
        xytext=(ipi1_src_x, faulter_top),
        arrowprops=arrow_kw,
    )
    mid_x1 = (ipi1_src_x + ipi1_dst_x) / 2
    ax.text(mid_x1 - 350, mid_y1, "IPI", fontsize=11, color="#2c3e50",
            weight="bold", ha="center", va="center")

    # IPI #2: handler → faulter (downward)
    ax.annotate(
        "", xy=(ipi2_dst_x, faulter_top),
        xytext=(ipi2_src_x, handler_bot),
        arrowprops=arrow_kw,
    )
    mid_x2 = (ipi2_src_x + ipi2_dst_x) / 2
    ax.text(mid_x2 + 350, mid_y1, "IPI", fontsize=11, color="#2c3e50",
            weight="bold", ha="center", va="center")

    # --- Curly brace helper (quadratic Bezier "{" shape) ---
    def draw_brace(ax, x0, x1, y_base, height, label):
        """Draw a horizontal curly brace from x0 to x1, tip pointing up."""
        mid = (x0 + x1) / 2
        span = x1 - x0
        q = span * 0.1
        ymid = y_base + height * 0.5
        ytop = y_base + height

        verts = [
            (x0, y_base),
            (x0, ymid),       (x0 + q, ymid),
            (mid, ymid),      (mid, ytop),
            (mid, ymid),      (x1 - q, ymid),
            (x1, ymid),       (x1, y_base),
        ]
        codes = [
            Path.MOVETO,
            Path.CURVE3, Path.CURVE3,
            Path.CURVE3, Path.CURVE3,
            Path.CURVE3, Path.CURVE3,
            Path.CURVE3, Path.CURVE3,
        ]
        ax.add_patch(PathPatch(
            Path(verts, codes), facecolor="none", edgecolor="#2c3e50",
            linewidth=1.2, clip_on=False,
        ))
        ax.text(mid, ytop + 0.04, label,
                ha="center", va="bottom", fontsize=12, weight="bold",
                color="#2c3e50")

    brace_y = lane_y["handler"] + bar_h / 2 + 0.04
    brace_h = 0.20

    # Curly brace above the three read() sub-phases
    read_x0 = sum(p[1] for p in handler_phases[:3])
    read_x1 = sum(p[1] for p in handler_phases[:6])
    draw_brace(ax, read_x0, read_x1, brace_y, brace_h, "read()")

    # Curly brace above the ioctl section (entry → return)
    ioctl_x0 = sum(p[1] for p in handler_phases[:7])
    ioctl_x1 = sum(p[1] for p in handler_phases[:12])
    draw_brace(ax, ioctl_x0, ioctl_x1, brace_y, brace_h, "ioctl()")

    # --- Lane labels ---
    ax.text(-total * 0.01, lane_y["faulter"], "Faulting\nThread",
            ha="right", va="center", fontsize=12, weight="bold")
    ax.text(-total * 0.01, lane_y["handler"], "Handler\nThread",
            ha="right", va="center", fontsize=12, weight="bold")

    # --- Legend for categories ---
    # --- Compute per-category % of critical-path time ---
    # Exclude idle phases and the overlapping ioctl return (h_4b)
    cat_ns = {}
    for label, dur, cat in faulter_phases + handler_phases:
        if cat == "idle":
            continue
        if label == "ioctl\nreturn":
            continue
        cat_ns[cat] = cat_ns.get(cat, 0) + dur
    cat_total = sum(cat_ns.values())

    def pct(cat):
        return 100.0 * cat_ns.get(cat, 0) / cat_total if cat_total else 0

    from matplotlib.patches import Patch
    legend_items = [
        Patch(facecolor=CAT_COLORS["fault"],     label=f"#PF paths ({pct('fault'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["plumbing"],  label=f"uffd protocol ({pct('plumbing'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["sched"],     label=f"Scheduling + IPI ({pct('sched'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["syscall"],   label=f"Syscall crossings ({pct('syscall'):.0f}%)"),
        Patch(facecolor=CAT_COLORS["page"],      label=f"Page setup ({pct('page'):.0f}%)"),
    ]
    # --- Axes ---
    ax.set_xlim(-total * 0.10, total * 1.02)
    ax.set_ylim(-0.55, 1.7)
    ax.set_yticks([])

    # Show µs on x-axis (more natural for the scale)
    us_ticks = np.arange(0, total / 1000 + 1, 2)
    ax.set_xticks(us_ticks * 1000)
    ax.set_xticklabels([f"{v:.0f}" for v in us_ticks])
    ax.set_xlabel("Time (\u00b5s)", fontsize=16)
    ax.tick_params(axis="x", labelsize=16)

    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    # Legend above the plot
    ax.legend(
        handles=legend_items, loc="upper center",
        bbox_to_anchor=(0.5, 1.25), ncol=5, fontsize=11,
        frameon=False, handlelength=1.2, handletextpad=0.4,
        columnspacing=1.0,
    )

    fig.tight_layout()
    fig.savefig(output, metadata={"creationDate": None}, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Plot userfaultfd overhead breakdown timeline")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input CSV results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    avgs = load_overhead_csv(args.input)
    faulter_phases, handler_phases = build_timeline(avgs)

    print("Faulter phases:", file=sys.stderr)
    t = 0
    for label, dur, cat in faulter_phases:
        flat = label.replace("\n", " ")
        print(f"  [{t:6.0f} → {t+dur:6.0f}]  {dur:5.0f} ns  {flat:20s}  ({cat})",
              file=sys.stderr)
        t += dur

    print(f"\nHandler phases:", file=sys.stderr)
    t = 0
    for label, dur, cat in handler_phases:
        flat = label.replace("\n", " ")
        print(f"  [{t:6.0f} → {t+dur:6.0f}]  {dur:5.0f} ns  {flat:20s}  ({cat})",
              file=sys.stderr)
        t += dur

    print(f"\nTotal critical-path latency: "
          f"{sum(p[1] for p in faulter_phases):.0f} ns", file=sys.stderr)

    plot_timeline(avgs, args.output)
    print(f"Plot saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
