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


def plot_one_timeseries(run: dict, ts_rows: list[dict], mode: str,
                        out_path: str,
                        ylim_thr: float | None = None,
                        log_latency: bool = False):
    """Draw one timeline in the bpf-fault-paper firecracker style:

      - left y-axis : Throughput (ops/s), blue solid line, K-formatted ticks
      - right y-axis: Latency (ms), orange solid "P99 Latency" line
      - gray solid vertical lines at snapshot Start/End
      - red hatched span over the Downtime window (freeze for live/live_bpf,
        the whole pause for full)
      - legend lower-left, large fonts, no title

    ylim_thr: shared upper throughput limit (raw ops/s) for
    consistent cross-plot comparison.
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter

    xs  = [r["t_rel_s"] for r in ts_rows]
    thr = [0.0 if r["failed"] else r["throughput"] for r in ts_rows]
    p99 = [r["p99_ms"] for r in ts_rows]

    fig, ax_thr = plt.subplots(figsize=(8, 4))
    ax_lat = ax_thr.twinx()

    # Throughput (left, blue) and P99 latency (right, orange).
    ax_thr.plot(xs, thr, color="steelblue", linewidth=1.8,
                label="Throughput", zorder=3)
    ax_lat.plot(xs, p99, color="darkorange", linewidth=1.8,
                label="P99 Latency", zorder=2)

    # Start/End vertical lines + Downtime band.
    res = run["results"]
    snap_s   = res.get("ts_snap_start_s",  0)
    snap_e   = res.get("ts_snap_end_s",    0)
    freeze_s = res.get("ts_freeze_start_s", 0)
    freeze_e = res.get("ts_freeze_end_s",   0)
    if snap_s and snap_e:
        for x in (snap_s, snap_e):
            ax_thr.axvline(x, color="dimgray", linewidth=2.0, zorder=4)
        down_s, down_e = (snap_s, snap_e) if mode == "full" \
            else (freeze_s, freeze_e)
        if down_e and down_e > down_s:
            ax_thr.axvspan(down_s, down_e, facecolor="firebrick",
                           alpha=0.25, hatch="//", edgecolor="firebrick",
                           zorder=1)

    # Left axis (Throughput, ops/s, K-formatted).
    ax_thr.set_xlabel("Time (s)", fontsize=LABEL_FONTSIZE)
    ax_thr.set_ylabel("Throughput (ops/s)", fontsize=LABEL_FONTSIZE)
    ax_thr.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    ax_thr.set_ylim(0, (ylim_thr * 1.1) if ylim_thr else max(thr) * 1.25)
    ax_thr.set_xlim(0, (snap_e + 1.5) if snap_e else max(xs))
    ax_thr.tick_params(labelsize=FONTSIZE)
    ax_thr.grid(True, alpha=0.3)

    # Right axis (Latency, ms).
    ax_lat.set_ylabel("Latency (ms)", fontsize=LABEL_FONTSIZE)
    if log_latency:
        ax_lat.set_yscale("log")
    else:
        ax_lat.set_ylim(0, YLIM_LAT_MS)
    ax_lat.tick_params(labelsize=FONTSIZE)

    # Legend with proxy artists for the markers (lower-left).
    handles = [
        Line2D([], [], color="steelblue", lw=1.8, label="Throughput"),
        Line2D([], [], color="dimgray", lw=2.0, label="Start/End"),
        Patch(facecolor="firebrick", alpha=0.25, hatch="//",
              edgecolor="firebrick", label="Downtime"),
        Line2D([], [], color="darkorange", lw=1.8, label="P99 Latency"),
    ]
    ax_thr.legend(handles=handles, fontsize=LEGEND_FONTSIZE,
                  loc="lower left", framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight",
                metadata={"creationDate": None})
    plt.close(fig)
    print(f"  Saved: {out_path}")


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
    args = ap.parse_args()

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
        for mode in MODE_ORDER:
            matched = [r for r in select(runs, mode=mode, mem_size_mib=mem)
                       if r["results"].get("timeseries_file")]
            if not matched:
                print(f"error: no timeseries data for mode={mode} mem={mem}",
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
                out_path = os.path.join(
                    args.outdir,
                    f"{MODE_PANELS[mode]}_{mem}mib_{mode}_iter{iteration}.pdf")
                plot_one_timeseries(run, ts_rows, mode, out_path,
                                    ylim_thr=ylim_thr,
                                    log_latency=args.log_latency)
                plotted += 1

            if not plotted:
                print(f"error: no plottable timeseries for mode={mode} "
                      f"mem={mem}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
