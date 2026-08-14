#!/usr/bin/env python3
# Plot snapshot timeline figures (Figure 8): throughput and P99 latency
# over time while a snapshot is taken, one figure per (memory size,
# snapshot mode, iteration).
#
# Output files: <outdir>/figure8<panel>_<mem>mib_<mode>_iter<N>.pdf
# where the panel letter follows the paper's layout: full -> 8a,
# live -> 8b, live_bpf -> 8c.
#
# Usage:
#   ./plot_snapshot_timeseries.py ../results/snapshot_benchmark_redis_heavy.json
#   ./plot_snapshot_timeseries.py ../results/snapshot_benchmark_redis_heavy.json \
#       --mem 8192 --outdir ../figures/snapshot_timeseries

import argparse
import os
import sys

import matplotlib.pyplot as plt

from snapshot_lib import (
    FONTSIZE, LABEL_FONTSIZE, LEGEND_FONTSIZE, MODE_ORDER,
    _compute_global_limits, _load_timeseries, detect_mem_sizes,
    load_runs, select,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTDIR = os.path.join(SCRIPT_DIR, "../figures/snapshot_timeseries")

# Paper panel letter per mode (Figure 8 layout)
MODE_PANELS = {"full": "figure8a", "live": "figure8b", "live_bpf": "figure8c"}

# Fixed latency axis top (ms), shared by all panels
YLIM_LAT_MS = 450

# --- paper mode -----------------------------------------------------
#
# In paper mode the three panels sit side by side, so each y-axis is
# drawn exactly once: throughput on the left panel, latency on the right
# panel, neither on the middle one. A side without a label loses its
# tick labels too, as in the original figures.
PAPER_YLABELS = {"full": "thr", "live": None, "live_bpf": "lat"}

# Axes geometry in inches. Paper mode places the axes explicitly rather
# than cropping with bbox_inches="tight", so that the data area alone
# carries the width difference between runs: a panel covering less time
# comes out narrower rather than stretched.
#
# The axes match the original figures' physical size, so that the element
# sizes below can be used exactly as the originals specified them.
PAPER_AXES_H     = 4.80
PAPER_AXES_W_MAX = 10.30  # data-area width of the longest panel
PAPER_MARGIN_B   = 1.12
PAPER_MARGIN_T   = 0.15
# Side margins depend on whether that side carries an axis label; only
# the data area has to stay proportional, so the margins need not match.
PAPER_MARGIN_L_LABEL = 1.45
PAPER_MARGIN_L_BARE  = 0.12   # no label and no ticks: just the spine
PAPER_MARGIN_R_LABEL = 1.25
PAPER_MARGIN_R_BARE  = 0.12

# X ticks every 2 s, latency ticks every 100 ms, as whole numbers --
# matching the original figures.
PAPER_XTICK_STEP     = 2
PAPER_LAT_TICK_STEP  = 100

# Throughput axis top (ops/s). The shared limit derived from the data
# lands just above 120K, which puts a 120K tick at the very top of the
# axis; capping just above the observed peak (~109K) stops at 100K.
# Raise this if a run ever exceeds it -- the traces would be clipped.
PAPER_YLIM_THR = 110_000

# Paper-mode element sizes, taken verbatim from the original figures
# (read out of their PDFs: 34/24/20pt type, 3/4pt strokes). Every element
# is specified at the same physical scale as the original, so LaTeX
# scales type and strokes together and nothing needs per-element
# compensation. Do not "fix" one of these in isolation to correct how a
# panel looks after scaling -- change the panel's \includegraphics width
# instead, or every other element silently goes out of proportion.
#
# These are deliberately not the shared FONTSIZE / LABEL_FONTSIZE /
# LEGEND_FONTSIZE, which other figures use at a smaller physical size.
PAPER_FONTSIZE        = 24
PAPER_LABEL_FONTSIZE  = 34
PAPER_LEGEND_FONTSIZE = 20
PAPER_LINEWIDTH       = 3.0   # throughput / latency traces
PAPER_VLINE_WIDTH     = 4.0   # snapshot start/end markers


def plot_one_timeseries(run: dict, ts_rows: list[dict], mode: str,
                        out_path: str,
                        ylim_thr: float | None = None,
                        log_latency: bool = False,
                        paper: bool = False,
                        secs_per_inch: float | None = None):
    """Draw one timeline in the bpf-fault-paper firecracker style:

      - left y-axis : Throughput (ops/s), blue solid line, K-formatted ticks
      - right y-axis: Latency (ms), orange solid "P99 Latency" line
      - gray solid vertical lines at snapshot Start/End
      - red hatched span over the Downtime window (freeze for live/live_bpf,
        the whole pause for full)
      - legend lower-left, large fonts, no title

    ylim_thr: shared upper throughput limit (raw ops/s) for
    consistent cross-plot comparison.

    paper: draw the trimmed side-by-side variant (see PAPER_YLABELS).
    secs_per_inch: paper mode only -- shared time-to-width scale, so a
    run covering less time yields a narrower panel.
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter

    fs_tick   = PAPER_FONTSIZE        if paper else FONTSIZE
    fs_label  = PAPER_LABEL_FONTSIZE  if paper else LABEL_FONTSIZE
    fs_legend = PAPER_LEGEND_FONTSIZE if paper else LEGEND_FONTSIZE
    lw_data   = PAPER_LINEWIDTH   if paper else 1.8
    lw_vline  = PAPER_VLINE_WIDTH if paper else 2.0

    xs  = [r["t_rel_s"] for r in ts_rows]
    thr = [0.0 if r["failed"] else r["throughput"] for r in ts_rows]
    p99 = [r["p99_ms"] for r in ts_rows]

    res_x = run["results"]
    xmax = (res_x.get("ts_snap_end_s", 0) + 1.5) or max(xs)

    if paper:
        margin_l = (PAPER_MARGIN_L_LABEL if PAPER_YLABELS[mode] == "thr"
                    else PAPER_MARGIN_L_BARE)
        margin_r = (PAPER_MARGIN_R_LABEL if PAPER_YLABELS[mode] == "lat"
                    else PAPER_MARGIN_R_BARE)
        axes_w = xmax / secs_per_inch
        fig_w  = axes_w + margin_l + margin_r
        fig_h  = PAPER_AXES_H + PAPER_MARGIN_B + PAPER_MARGIN_T
        fig = plt.figure(figsize=(fig_w, fig_h))
        ax_thr = fig.add_axes([margin_l / fig_w,
                               PAPER_MARGIN_B / fig_h,
                               axes_w / fig_w,
                               PAPER_AXES_H / fig_h])
    else:
        fig, ax_thr = plt.subplots(figsize=(8, 4))
    ax_lat = ax_thr.twinx()

    # Throughput (left, blue) and P99 latency (right, orange).
    ax_thr.plot(xs, thr, color="steelblue", linewidth=lw_data,
                label="Throughput", zorder=3)
    ax_lat.plot(xs, p99, color="darkorange", linewidth=lw_data,
                label="P99 Latency", zorder=2)

    # Start/End vertical lines + Downtime band.
    res = run["results"]
    snap_s   = res.get("ts_snap_start_s",  0)
    snap_e   = res.get("ts_snap_end_s",    0)
    freeze_s = res.get("ts_freeze_start_s", 0)
    freeze_e = res.get("ts_freeze_end_s",   0)
    if snap_s and snap_e:
        for x in (snap_s, snap_e):
            ax_thr.axvline(x, color="dimgray", linewidth=lw_vline, zorder=4)
        down_s, down_e = (snap_s, snap_e) if mode == "full" \
            else (freeze_s, freeze_e)
        if down_e and down_e > down_s:
            ax_thr.axvspan(down_s, down_e, facecolor="firebrick",
                           alpha=0.25, hatch="//", edgecolor="firebrick",
                           zorder=1)

    # Left axis (Throughput, ops/s, K-formatted).
    ax_thr.set_xlabel("Time (s)", fontsize=fs_label)
    if not paper or PAPER_YLABELS[mode] == "thr":
        ax_thr.set_ylabel("Throughput (ops/s)", fontsize=fs_label)
    ax_thr.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    if paper:
        if max(thr) > PAPER_YLIM_THR:
            print(f"  warning: {mode} peaks at {max(thr):,.0f} ops/s, above "
                  f"PAPER_YLIM_THR={PAPER_YLIM_THR:,} -- trace clipped",
                  file=sys.stderr)
        ax_thr.set_ylim(0, PAPER_YLIM_THR)
    else:
        ax_thr.set_ylim(0, (ylim_thr * 1.1) if ylim_thr else max(thr) * 1.25)
    ax_thr.set_xlim(0, xmax)
    if paper:
        from matplotlib.ticker import MultipleLocator
        ax_thr.xaxis.set_major_locator(MultipleLocator(PAPER_XTICK_STEP))
        ax_thr.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax_thr.tick_params(labelsize=fs_tick)
    if paper and PAPER_YLABELS[mode] != "thr":
        ax_thr.tick_params(axis="y", left=False, labelleft=False)
    ax_thr.grid(True, alpha=0.3)

    # Right axis (Latency, ms).
    if not paper or PAPER_YLABELS[mode] == "lat":
        ax_lat.set_ylabel("Latency (ms)", fontsize=fs_label)
    if log_latency:
        ax_lat.set_yscale("log")
    else:
        ax_lat.set_ylim(0, YLIM_LAT_MS)
    ax_lat.tick_params(labelsize=fs_tick)
    if paper and not log_latency:
        from matplotlib.ticker import MultipleLocator as _ML
        ax_lat.yaxis.set_major_locator(_ML(PAPER_LAT_TICK_STEP))
    if paper and PAPER_YLABELS[mode] != "lat":
        ax_lat.tick_params(axis="y", right=False, labelright=False)

    # Legend with proxy artists for the markers (lower-left).
    handles = [
        Line2D([], [], color="steelblue", lw=lw_data, label="Throughput"),
        Line2D([], [], color="dimgray", lw=lw_vline, label="Start/End"),
        Patch(facecolor="firebrick", alpha=0.25, hatch="//",
              edgecolor="firebrick", label="Downtime"),
        Line2D([], [], color="darkorange", lw=lw_data, label="P99 Latency"),
    ]
    ax_thr.legend(handles=handles, fontsize=fs_legend,
                  loc="lower left", framealpha=0.9)

    if paper:
        # No tight_layout/bbox cropping: the axes rectangle is placed by
        # hand so the data area stays exactly proportional to the time
        # span across panels.
        fig.savefig(out_path, dpi=150, metadata={"creationDate": None})
    else:
        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches="tight",
                    metadata={"creationDate": None})
    plt.close(fig)
    print(f"  Saved: {out_path}"
          + (f"  [{xmax:.1f}s span]" if paper else ""))


def main():
    ap = argparse.ArgumentParser(
        description="Plot per-iteration snapshot timelines (Figure 8).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("json", help="Path to snapshot_benchmark_<workload>.json")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR,
                    help="Output directory")
    ap.add_argument("--mem", type=int, nargs="+", metavar="MiB",
                    help="Memory sizes to plot (default: all in the JSON)")
    ap.add_argument("--log-latency", action="store_true",
                    help="Use log scale for the latency axis")
    ap.add_argument("--paper", action="store_true",
                    help="Paper mode: one y-label per panel and a shared "
                         "time-to-width scale (needs --iters)")
    ap.add_argument("--iters", metavar="MODE=ITER[,...]",
                    help="Plot only these (mode, iteration) panels, "
                         "e.g. full=1,live=2,live_bpf=1")
    args = ap.parse_args()

    want = None
    if args.iters:
        want = {}
        for part in args.iters.split(","):
            mode, _, it = part.partition("=")
            mode = mode.strip()
            if mode not in MODE_ORDER or not it.strip().isdigit():
                print(f"error: bad --iters entry '{part}', expected one of "
                      f"{'/'.join(MODE_ORDER)}=<iteration>", file=sys.stderr)
                sys.exit(1)
            want[mode] = int(it)
    if args.paper and not want:
        print("error: --paper needs --iters to pick one panel per mode",
              file=sys.stderr)
        sys.exit(1)

    runs = load_runs(args.json)
    if not runs:
        print("error: no records in JSON", file=sys.stderr)
        sys.exit(1)

    # results/timeseries/ lives next to the JSON
    results_dir = os.path.dirname(os.path.abspath(args.json))
    mem_sizes = sorted(set(args.mem)) if args.mem else detect_mem_sizes(runs)

    os.makedirs(args.outdir, exist_ok=True)

    # Shared y-axis limits across every plot, for cross-plot comparison.
    ylim_thr, _ = _compute_global_limits(runs, results_dir)

    for mem in mem_sizes:
        # Paper mode shares one time-to-width scale across the panels, so
        # the longest span has to be known before anything is drawn.
        secs_per_inch = None
        if args.paper:
            spans = []
            for mode, it in want.items():
                for r in select(runs, mode=mode, mem_size_mib=mem):
                    if r["config"].get("iteration", 0) == it:
                        spans.append(r["results"].get("ts_snap_end_s", 0) + 1.5)
            if not spans:
                print(f"error: no runs matching --iters at mem={mem}",
                      file=sys.stderr)
                sys.exit(1)
            secs_per_inch = max(spans) / PAPER_AXES_W_MAX

        for mode in MODE_ORDER:
            if want and mode not in want:
                continue
            matched = [r for r in select(runs, mode=mode, mem_size_mib=mem)
                       if r["results"].get("timeseries_file")]
            if want:
                matched = [r for r in matched
                           if r["config"].get("iteration", 0) == want[mode]]
            if not matched:
                print(f"error: no timeseries data for mode={mode} mem={mem}"
                      + (f" iteration={want[mode]}" if want else ""),
                      file=sys.stderr)
                sys.exit(1)

            plotted = 0
            for run in sorted(matched,
                              key=lambda r: r["config"].get("iteration", 0)):
                iteration = run["config"].get("iteration", 0)
                ts_path = os.path.join(results_dir,
                                       run["results"]["timeseries_file"])
                if not os.path.exists(ts_path):
                    print(f"warning: {ts_path} not found, skipping "
                          f"iteration {iteration}", file=sys.stderr)
                    continue
                ts_rows = _load_timeseries(ts_path)
                if not ts_rows:
                    print(f"warning: {ts_path} has no samples, skipping "
                          f"iteration {iteration}", file=sys.stderr)
                    continue
                suffix = "_paper" if args.paper else ""
                out_path = os.path.join(
                    args.outdir,
                    f"{MODE_PANELS[mode]}_{mem}mib_{mode}"
                    f"_iter{iteration}{suffix}.pdf")
                plot_one_timeseries(run, ts_rows, mode, out_path,
                                    ylim_thr=ylim_thr,
                                    log_latency=args.log_latency,
                                    paper=args.paper,
                                    secs_per_inch=secs_per_inch)
                plotted += 1

            if not plotted:
                print(f"error: no plottable timeseries for mode={mode} "
                      f"mem={mem}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
