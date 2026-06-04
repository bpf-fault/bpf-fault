#!/usr/bin/env python3
"""benchplot — unified benchmark plotting CLI.

CSV-based paper-ready charts:
  benchplot --type snapshot-time --data data.csv --output chart.pdf
  benchplot --type latency       --data lat.csv  --output lat.pdf --log-y
  benchplot --type timeseries    --data ts.csv   --output ts.pdf \\
            --snap-start 5.0 --snap-end 7.0 --freeze-start 5.2 --freeze-end 6.8

Paper figures (graphs 1, 2, 4) from benchmark JSON:
  benchplot --paper [--results-dir DIR] [--out-dir DIR] [--fc-mem MiB]
  benchplot --paper --graphs 1 2          # only graphs 1 & 2

Working examples (generates sample CSVs + all chart types):
  benchplot benchplot-example [--outdir DIR]
"""

import argparse
import csv
import json as _json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

DEFAULT_COLORS = [
    "steelblue",
    "darkorange",
    "firebrick",
    "forestgreen",
    "mediumpurple",
    "saddlebrown",
    "deeppink",
    "dimgray",
    "olive",
    "teal",
]

_CHART_DEFAULTS = {
    "snapshot-time": dict(
        series=["Synchronous", "userfaultfd"],
        y_label="Total Snapshot Time (s)",
        log_y=False,
        colors=["steelblue", "darkorange"],
    ),
    "downtime": dict(
        series=["Synchronous", "userfaultfd"],
        y_label="Downtime (s)",
        log_y=False,
        colors=["steelblue", "darkorange"],
    ),
    "throughput": dict(
        series=["userfaultfd", "bpf_fault"],
        y_label="Throughput (ops/s)",
        log_y=False,
        colors=["steelblue", "forestgreen"],
    ),
    "latency": dict(
        series=["userfaultfd", "bpf_fault"],
        y_label="Latency (ms)",
        log_y=True,
        colors=["steelblue", "forestgreen"],
    ),
}


# ---------------------------------------------------------------------------
# Shared helpers (importable by plot_snapshot_benchmark.py)
# ---------------------------------------------------------------------------

def _savefig(fig, path: str, dpi: int = 150):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    print(f"  Saved: {path}")


def _rolling_mean(xs, ys, window_s=0.5):
    xs = np.array(xs, dtype=float)
    ys = np.array(ys, dtype=float)
    out = np.empty_like(ys)
    half = window_s / 2
    for i, t in enumerate(xs):
        mask = (xs >= t - half) & (xs <= t + half)
        out[i] = ys[mask].mean() if mask.any() else ys[i]
    return xs, out


def _smooth_with_gaps(xs, ys, window_s=0.5, gap_thresh_s=1.0):
    if not xs:
        return [], []
    _, ys_s = _rolling_mean(xs, ys, window_s=window_s)
    out_xs, out_ys = [xs[0]], [ys_s[0]]
    for i in range(1, len(xs)):
        if xs[i] - xs[i - 1] > gap_thresh_s:
            out_xs.append(float("nan"))
            out_ys.append(float("nan"))
        out_xs.append(float(xs[i]))
        out_ys.append(float(ys_s[i]))
    return out_xs, out_ys


# ---------------------------------------------------------------------------
# Shared renderers (importable by other scripts)
# ---------------------------------------------------------------------------

def render_grouped_bars(
    groups,
    series_names,
    series_values,
    series_errors=None,
    y_label="",
    output="chart.pdf",
    log_y=False,
    width=4,
    height=3,
    dpi=150,
    bar_width=0.35,
    colors=None,
    legend_loc="upper right",
    fontsize=11,
    label_fontsize=None,
):
    """Render a grouped bar chart and save to *output*.

    Args:
        groups:        x-axis category labels (support literal \\n for multiline).
        series_names:  legend labels, one per series.
        series_values: list[list[float]], series_values[i][j] = series i, group j.
        series_errors: optional list[list[float]] for ±std error bars.
        output:        file path; format inferred from extension (.pdf/.png/.svg).
    """
    if colors is None:
        colors = DEFAULT_COLORS
    if label_fontsize is None:
        label_fontsize = fontsize + 1

    n_series = len(series_names)
    x = np.arange(len(groups))

    fig, ax = plt.subplots(figsize=(width, height))

    for i, (name, vals) in enumerate(zip(series_names, series_values)):
        offset = (i - (n_series - 1) / 2) * bar_width
        errs = series_errors[i] if series_errors else None
        kwargs = dict(width=bar_width, label=name, color=colors[i % len(colors)])
        if errs is not None:
            kwargs.update(yerr=errs, capsize=3)
        ax.bar(x + offset, vals, **kwargs)

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=fontsize)
    ax.tick_params(axis="y", labelsize=fontsize)
    ax.set_ylabel(y_label, fontsize=label_fontsize)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc=legend_loc, fontsize=fontsize)

    if log_y:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.LogFormatterMathtext())
    else:
        ax.set_ylim(bottom=0)

    fig.tight_layout()
    _savefig(fig, output, dpi=dpi)


def render_timeseries(
    rows,
    output="timeseries.pdf",
    snap_start=None,
    snap_end=None,
    freeze_start=None,
    freeze_end=None,
    log_latency=False,
    ylim_thr=None,
    ylim_lat=None,
    width=8,
    height=4,
    dpi=150,
    thr_label="Throughput (ops/s)",
    lat_label="Latency (ms)",
):
    """Render a dual-axis throughput + latency timeseries and save to *output*.

    Args:
        rows: list of dicts with keys: t_rel_s, throughput, avg_ms, p99_ms,
              and optionally failed (int 0/1).
    """
    ok_rows   = [r for r in rows if not r.get("failed")]
    xs_ok     = [r["t_rel_s"]    for r in ok_rows]
    ys_ok     = [r["throughput"] for r in ok_rows]
    avg_ms    = [r["avg_ms"]     for r in ok_rows]
    p99_ms    = [r["p99_ms"]     for r in ok_rows]
    xs_all    = [r["t_rel_s"]    for r in rows]
    ys_all    = [0.0 if r.get("failed") else r["throughput"] for r in rows]
    failed_xs = [r["t_rel_s"] for r in rows if r.get("failed")]

    fig, ax_thr = plt.subplots(figsize=(width, height))
    ax_lat = ax_thr.twinx()

    ax_thr.scatter(xs_ok, ys_ok, s=4, color="steelblue", alpha=0.4,
                   label="throughput raw")
    if xs_all:
        _, ys_s = _rolling_mean(xs_all, ys_all)
        ax_thr.plot(xs_all, ys_s, color="steelblue", linewidth=2,
                    label="throughput (smoothed)")
    if failed_xs:
        ax_thr.scatter(failed_xs, [0.0] * len(failed_xs), s=40,
                       color="firebrick", marker="x", linewidths=1.5,
                       zorder=5, label="failed")

    if xs_ok:
        avg_sx, avg_sy = _smooth_with_gaps(xs_ok, avg_ms)
        p99_sx, p99_sy = _smooth_with_gaps(xs_ok, p99_ms)
        ax_lat.scatter(xs_ok, avg_ms, s=4, color="forestgreen", alpha=0.3)
        ax_lat.scatter(xs_ok, p99_ms, s=4, color="darkorange",  alpha=0.3)
        ax_lat.plot(avg_sx, avg_sy, color="forestgreen", linewidth=2,
                    linestyle="--", label="avg latency")
        ax_lat.plot(p99_sx, p99_sy, color="darkorange", linewidth=2,
                    linestyle=":",  label="p99 latency")

    if snap_start and snap_end:
        for ax in (ax_thr, ax_lat):
            ax.axvline(snap_start, color="steelblue", linestyle="--",
                       linewidth=1, alpha=0.7)
            ax.axvline(snap_end,   color="steelblue", linestyle="--",
                       linewidth=1, alpha=0.7)
    if freeze_start and freeze_end and freeze_end > freeze_start:
        for ax in (ax_thr, ax_lat):
            ax.axvspan(freeze_start, freeze_end, alpha=0.15,
                       color="firebrick", hatch="//", label="_nolegend_")

    ax_thr.set_xlabel("Time (s)", fontsize=12)
    ax_thr.set_ylabel(thr_label, fontsize=12, color="steelblue")
    ax_thr.tick_params(axis="y", labelcolor="steelblue")
    ax_thr.grid(True, alpha=0.3)
    if ylim_thr is not None:
        ax_thr.set_ylim(0, ylim_thr * 1.1)
    else:
        ax_thr.set_ylim(bottom=0)

    ax_lat.set_ylabel(lat_label, fontsize=12, color="dimgray")
    ax_lat.tick_params(axis="y", labelcolor="dimgray")
    if log_latency:
        ax_lat.set_yscale("log")
    elif ylim_lat is not None:
        ax_lat.set_ylim(0, ylim_lat * 1.1)
    else:
        ax_lat.set_ylim(bottom=0)

    lines_thr, labels_thr = ax_thr.get_legend_handles_labels()
    lines_lat, labels_lat = ax_lat.get_legend_handles_labels()
    ax_thr.legend(lines_thr + lines_lat, labels_thr + labels_lat,
                  fontsize=10, loc="upper left")

    fig.tight_layout()
    _savefig(fig, output, dpi=dpi)


# ---------------------------------------------------------------------------
# CSV parsers
# ---------------------------------------------------------------------------

def _parse_bar_csv(path, series_override=None, x_labels_override=None):
    """Parse a grouped bar chart CSV. Returns (groups, series_names, series_values).

    CSV format:
        label_col, Series A, Series B, ...
        4 GB, 5.2, 1.8
        8 GB, 5.8, 2.1

    The first column provides x-axis group labels unless overridden.
    Supports \\n (literal backslash-n) in label strings for multiline ticks.
    """
    df = pd.read_csv(path)
    if x_labels_override:
        groups = [lbl.replace("\\n", "\n") for lbl in x_labels_override]
    else:
        groups = [str(v).replace("\\n", "\n") for v in df.iloc[:, 0]]

    cols = series_override if series_override else list(df.columns[1:])
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Series not found in CSV columns {list(df.columns)}: {missing}")

    series_values = [df[c].tolist() for c in cols]
    return groups, cols, series_values


def _parse_timeseries_csv(path):
    """Parse a timeseries CSV. Returns list[dict] with keys matching render_timeseries rows."""
    df = pd.read_csv(path)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "t_rel_s":    float(row["t_rel_s"]),
            "throughput": float(row["throughput"]),
            "avg_ms":     float(row.get("avg_ms",  0) or 0),
            "p99_ms":     float(row.get("p99_ms",  0) or 0),
            "failed":     int(row.get("failed",    0) or 0),
        })
    return rows


# Per-type figure size defaults (width, height) in inches
_TYPE_FIGSIZE = {
    "snapshot-time": (4, 3),
    "downtime":      (4, 3),
    "throughput":    (4, 3),
    "latency":       (4, 3),
    "timeseries":    (12, 6),
}


def _snap_times_from_json(json_path, csv_path):
    """Look up snap/freeze times in a benchmark JSON for a given timeseries CSV.

    Matches by CSV basename against the timeseries_file field in each run.
    Returns (snap_start, snap_end, freeze_start, freeze_end) or Nones if not found.
    """
    csv_basename = os.path.basename(csv_path)
    try:
        with open(json_path) as f:
            runs = _json.load(f)
    except (OSError, _json.JSONDecodeError) as e:
        print(f"  WARNING: could not read JSON {json_path}: {e}", file=sys.stderr)
        return None, None, None, None

    for run in runs:
        ts_file = run.get("results", {}).get("timeseries_file", "")
        if os.path.basename(ts_file) == csv_basename:
            res = run["results"]
            return (
                res.get("ts_snap_start_s"),
                res.get("ts_snap_end_s"),
                res.get("ts_freeze_start_s"),
                res.get("ts_freeze_end_s"),
            )
    print(f"  WARNING: no run in {json_path} matched timeseries file '{csv_basename}'",
          file=sys.stderr)
    return None, None, None, None


def _detect_snap_window(rows):
    """Heuristic: infer snapshot window from a sustained throughput drop.

    Uses the first 20 % of samples as the baseline. Marks the window where
    rolling throughput falls below 60 % of baseline. Freeze sub-window is
    taken from the contiguous range of failed samples, if any.

    Returns (snap_start, snap_end, freeze_start, freeze_end) or Nones when
    no clear drop is found.
    """
    ok = [r for r in rows if not r.get("failed")]
    if len(ok) < 10:
        return None, None, None, None

    xs = np.array([r["t_rel_s"]    for r in ok])
    ys = np.array([r["throughput"] for r in ok])

    n_base   = max(3, len(ys) // 5)
    baseline = np.mean(ys[:n_base])
    if baseline <= 0:
        return None, None, None, None

    below = ys < baseline * 0.6
    if not below.any():
        return None, None, None, None

    start_idx  = int(np.where(below)[0][0])
    snap_start = float(xs[start_idx])

    # End of the first contiguous dip — first recovery above threshold after start_idx
    recovered = np.where(~below[start_idx:])[0]
    snap_end  = float(xs[start_idx + int(recovered[0])]) if len(recovered) else float(xs[below][-1])

    failed_ts = sorted(r["t_rel_s"] for r in rows if r.get("failed"))
    freeze_start = failed_ts[0]  if failed_ts else None
    freeze_end   = failed_ts[-1] if failed_ts else None

    return snap_start, snap_end, freeze_start, freeze_end


# ---------------------------------------------------------------------------
# Command: plot (CSV-based)
# ---------------------------------------------------------------------------

def cmd_plot(args):
    chart_type = args.type
    defaults   = _CHART_DEFAULTS.get(chart_type, {})

    # Apply per-type dimension defaults when the user didn't override
    default_w, default_h = _TYPE_FIGSIZE.get(chart_type, (4, 3))
    width  = args.width  if args.width  is not None else default_w
    height = args.height if args.height is not None else default_h

    if chart_type == "timeseries":
        rows = _parse_timeseries_csv(args.data)

        snap_start   = args.snap_start
        snap_end     = args.snap_end
        freeze_start = args.freeze_start
        freeze_end   = args.freeze_end

        # Auto-discover from JSON if provided
        if args.json:
            snap_start, snap_end, freeze_start, freeze_end = \
                _snap_times_from_json(args.json, args.data)
        # Heuristic fallback when no explicit times given
        elif snap_start is None and snap_end is None:
            snap_start, snap_end, freeze_start, freeze_end = \
                _detect_snap_window(rows)
            if snap_start is not None:
                print(f"  Auto-detected snapshot window: "
                      f"{snap_start:.2f}s – {snap_end:.2f}s")

        render_timeseries(
            rows,
            output=args.output,
            snap_start=snap_start,
            snap_end=snap_end,
            freeze_start=freeze_start,
            freeze_end=freeze_end,
            log_latency=args.log_y,
            width=width,
            height=height,
            dpi=args.dpi,
        )
        return

    series  = args.series  if args.series  else defaults.get("series",  [])
    y_label = args.y_label if args.y_label else defaults.get("y_label", "")
    log_y   = args.log_y   or defaults.get("log_y",   False)
    colors  = args.colors  if args.colors  else defaults.get("colors",  None)

    x_labels = args.x_labels if args.x_labels else None
    groups, series_names, series_values = _parse_bar_csv(
        args.data, series_override=series, x_labels_override=x_labels
    )

    render_grouped_bars(
        groups=groups,
        series_names=series_names,
        series_values=series_values,
        y_label=y_label,
        output=args.output,
        log_y=log_y,
        width=width,
        height=height,
        dpi=args.dpi,
        bar_width=args.bar_width,
        colors=colors,
    )


# ---------------------------------------------------------------------------
# Command: paper (JSON-based, wraps plot_graphs12 + plot_graph4)
# ---------------------------------------------------------------------------

def cmd_paper(args):
    _bench_dir = os.path.dirname(os.path.abspath(__file__))
    if _bench_dir not in sys.path:
        sys.path.insert(0, _bench_dir)

    # Lazy imports to avoid circular dependency at module level
    import plot_graphs12  # noqa: PLC0415
    import plot_graph4    # noqa: PLC0415

    graphs     = set(args.graphs)
    results_dir = args.results_dir
    out_dir    = args.out_dir
    fc_mem     = args.fc_mem

    os.makedirs(out_dir, exist_ok=True)

    if {1, 2} & graphs:
        print("=== Graphs 1 & 2: Downtime / Total Snapshot Time ===")
        plot_graphs12.main(results_dir=results_dir, out_dir=out_dir)

    if 4 in graphs:
        print("\n=== Graph 4: Throughput / Latency ===")
        all_runs = plot_graph4.load_all_runs(
            results_dir, plot_graph4._WORKLOAD_MAP, fc_mem
        )
        if not all_runs:
            print("ERROR: no runs loaded for graph 4 — check JSON files exist "
                  f"in {results_dir}", file=sys.stderr)
            return

        print(f"Loaded {len(all_runs)} runs")
        plot_graph4.plot_graph4(
            all_runs,
            baseline_fn=lambda r: r["results"]["throughput"]["baseline_ops_s"],
            during_fn=lambda r: r["results"]["throughput"]["during_ops_s"],
            ylabel="Avg Throughput During Snapshot",
            scale=1e6,
            unit="M ops/s",
            out_path=os.path.join(out_dir, "graph4_throughput.png"),
            workload_map=plot_graph4._WORKLOAD_MAP,
            fc_mem=fc_mem,
        )
        plot_graph4.plot_graph4(
            all_runs,
            baseline_fn=lambda r: r["results"]["latency_us"]["baseline_avg"],
            during_fn=lambda r: r["results"]["latency_us"]["during_avg"],
            ylabel="Avg Latency During Snapshot",
            scale=1.0,
            unit="µs",
            out_path=os.path.join(out_dir, "graph4_latency.png"),
            workload_map=plot_graph4._WORKLOAD_MAP,
            fc_mem=fc_mem,
        )

    print("\nDone.")


# ---------------------------------------------------------------------------
# Command: benchplot-example
# ---------------------------------------------------------------------------

_EXAMPLE_CSVS = {
    "snapshot-time": (
        "size,Synchronous,userfaultfd\n"
        "4 GB,5.2,1.8\n"
        "8 GB,5.8,2.1\n"
    ),
    "downtime": (
        "size,Synchronous,userfaultfd\n"
        "4 GB,3.8,0.019\n"
        "8 GB,3.9,0.019\n"
    ),
    "throughput": (
        "config,userfaultfd,bpf_fault\n"
        "Redis\\n4 GB,74000,76000\n"
        "Redis\\n8 GB,71000,73000\n"
        "Memcached\\n4 GB,88000,90000\n"
        "Memcached\\n8 GB,85000,87000\n"
    ),
    "latency": (
        "config,userfaultfd,bpf_fault\n"
        "Redis\\n4 GB,12.5,10.2\n"
        "Redis\\n8 GB,13.1,10.8\n"
        "Memcached\\n4 GB,8.3,6.9\n"
        "Memcached\\n8 GB,8.9,7.4\n"
    ),
}


def _make_timeseries_csv():
    """Generate a synthetic timeseries CSV with a simulated snapshot window."""
    rng = np.random.default_rng(42)
    rows = ["t_rel_s,throughput,avg_ms,p99_ms,failed"]
    for i in range(120):
        t = i * 0.1
        snap_active = 5.0 <= t <= 7.0
        thr   = rng.normal(50000 if snap_active else 75000, 3000)
        avg   = rng.normal(2.5   if snap_active else 1.2,   0.3)
        p99   = rng.normal(8.0   if snap_active else 3.5,   1.0)
        failed = 1 if (5.8 <= t <= 6.0) else 0
        if failed:
            rows.append(f"{t:.2f},0,0,0,1")
        else:
            rows.append(f"{t:.2f},{max(0, thr):.0f},{max(0, avg):.3f},"
                        f"{max(0, p99):.3f},0")
    return "\n".join(rows) + "\n"


def cmd_example(args):
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    print(f"Writing examples to: {outdir}\n")

    for chart_type, csv_content in _EXAMPLE_CSVS.items():
        csv_path = os.path.join(outdir, f"{chart_type}.csv")
        with open(csv_path, "w") as f:
            f.write(csv_content)
        print(f"  Wrote: {csv_path}")

        defaults = _CHART_DEFAULTS[chart_type]
        groups, series_names, series_values = _parse_bar_csv(csv_path)
        render_grouped_bars(
            groups=groups,
            series_names=series_names,
            series_values=series_values,
            y_label=defaults["y_label"],
            output=os.path.join(outdir, f"{chart_type}.pdf"),
            log_y=defaults["log_y"],
            colors=defaults["colors"],
        )

    ts_csv_path = os.path.join(outdir, "timeseries.csv")
    with open(ts_csv_path, "w") as f:
        f.write(_make_timeseries_csv())
    print(f"\n  Wrote: {ts_csv_path}")

    rows = _parse_timeseries_csv(ts_csv_path)
    render_timeseries(
        rows,
        output=os.path.join(outdir, "timeseries.pdf"),
        snap_start=5.0,
        snap_end=7.0,
        freeze_start=5.2,
        freeze_end=6.8,
    )

    print("\nAll examples written.")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Paper mode
    p.add_argument(
        "--paper",
        action="store_true",
        help="Generate paper figures (graphs 1, 2, 4) from benchmark JSON files",
    )
    p.add_argument(
        "--results-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"),
        metavar="DIR",
        help="Directory containing benchmark JSON files (--paper mode)",
    )
    p.add_argument(
        "--out-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"),
        metavar="DIR",
        help="Output directory for paper figures (--paper mode)",
    )
    p.add_argument(
        "--fc-mem",
        type=int,
        default=8192,
        metavar="MiB",
        help="FC memory size to include in graph 4 (--paper mode)",
    )
    p.add_argument(
        "--graphs",
        type=int,
        nargs="+",
        choices=[1, 2, 4],
        default=[1, 2, 4],
        metavar="{1,2,4}",
        help="Which paper graphs to generate (--paper mode, default: all)",
    )

    # CSV-based chart mode
    p.add_argument(
        "--type",
        choices=["snapshot-time", "downtime", "throughput", "latency", "timeseries"],
        metavar="TYPE",
        help="Chart type: snapshot-time | downtime | throughput | latency | timeseries",
    )
    p.add_argument("--data",   metavar="CSV",  help="Input CSV file")
    p.add_argument("--output", metavar="FILE", help="Output file (.pdf/.png/.svg)")

    # Style overrides
    p.add_argument("--series",   metavar="A,B",
                   type=lambda s: s.split(","),
                   help="Comma-separated series names (must match CSV column headers)")
    p.add_argument("--x-labels", metavar="A,B",
                   type=lambda s: s.split(","),
                   help="Comma-separated x-axis labels (overrides CSV first column)")
    p.add_argument("--y-label",  metavar="STR",  help="Y-axis label string")
    p.add_argument("--log-y",    action="store_true", help="Use log scale on y-axis")
    p.add_argument("--width",    type=float, default=None,
                   help="Figure width in inches (default: 12 for timeseries, 4 for bar charts)")
    p.add_argument("--height",   type=float, default=None,
                   help="Figure height in inches (default: 6 for timeseries, 3 for bar charts)")
    p.add_argument("--dpi",      type=int,   default=150,  help="Output DPI")
    p.add_argument("--bar-width",type=float, default=0.35, help="Width of individual bars")
    p.add_argument("--colors",   metavar="A,B",
                   type=lambda s: s.split(","),
                   help="Comma-separated hex or named colors for series")

    # Timeseries-specific
    p.add_argument("--json", metavar="FILE",
                   help="Benchmark JSON (snapshot_benchmark_*.json) to auto-read "
                        "snap/freeze times for --type timeseries")
    p.add_argument("--snap-start",   type=float,
                   help="Snapshot start (s); auto-detected if omitted")
    p.add_argument("--snap-end",     type=float,
                   help="Snapshot end (s); auto-detected if omitted")
    p.add_argument("--freeze-start", type=float,
                   help="Freeze window start (s); auto-detected from failed samples if omitted")
    p.add_argument("--freeze-end",   type=float,
                   help="Freeze window end (s); auto-detected from failed samples if omitted")

    # Example subcommand
    p.add_argument("_example_cmd", nargs="?", metavar="benchplot-example",
                   help=argparse.SUPPRESS)
    p.add_argument("--outdir", default="./benchplot-examples",
                   help="Output directory for benchplot-example")

    return p


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "benchplot-example":
        parser = argparse.ArgumentParser(
            description="Generate sample CSVs and charts for all chart types."
        )
        parser.add_argument("_cmd")
        parser.add_argument("--outdir", default="./benchplot-examples",
                            help="Output directory (default: ./benchplot-examples)")
        cmd_example(parser.parse_args())
        return

    parser = _build_parser()
    args = parser.parse_args()

    if args.paper:
        cmd_paper(args)
        return

    if not args.type:
        parser.error("one of --type or --paper or 'benchplot-example' is required")
    if not args.data:
        parser.error("--data is required")
    if not args.output:
        parser.error("--output is required")

    cmd_plot(args)


if __name__ == "__main__":
    main()
