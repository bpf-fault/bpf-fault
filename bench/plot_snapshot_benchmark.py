#!/usr/bin/env python3
"""Plot Firecracker snapshot benchmark results.

Reads a JSON file produced by run_snapshot_benchmark.py and generates:
  - total_snapshot_time.csv     full vs live total time, avg±std per mem size
  - downtime_comparison.csv     full vs live vs live_bpf downtime, avg±std
  - phase_breakdown.csv         per-phase µs avg per (mode, mem_size)
  - timeseries_<mem>mib_<mode>.png × 9   throughput + avg lat + p99 on dual y-axis
  - throughput_during_snapshot.png        avg ops/s during snapshot window

Usage:
    python3 plot_snapshot_benchmark.py results/snapshot_benchmark_redis_light.json
    python3 plot_snapshot_benchmark.py results/snapshot_benchmark_redis_light.json \\
        --outdir figures/
"""

import argparse
import csv
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Embed fonts as TrueType (Illustrator-editable) — matches bench_plot_lib.py
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"]  = 42

# bpf-fault default colour palette
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

MODE_LABELS = {
    "full":     "Full (sync)",
    "live":     "Live (UFFD)",
    "live_bpf": "Live (eBPF)",
}
MODE_ORDER  = ["full", "live", "live_bpf"]
MODE_COLORS = {
    "full":     DEFAULT_COLORS[2],   # firebrick
    "live":     DEFAULT_COLORS[0],   # steelblue
    "live_bpf": DEFAULT_COLORS[3],   # forestgreen
}

FONTSIZE       = 16
LABEL_FONTSIZE = 18
LEGEND_FONTSIZE = 14


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------

def load_runs(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def select(runs: list[dict], **config_match) -> list[dict]:
    """Return runs whose config contains all key=value pairs."""
    return [r for r in runs if all(r["config"].get(k) == v
                                   for k, v in config_match.items())]


def result_values(runs: list[dict], result_key: str,
                  **config_match) -> list[float]:
    """Extract result_key from all matching runs."""
    return [r["results"][result_key]
            for r in select(runs, **config_match)
            if result_key in r["results"]]


def agg(vals: list[float]) -> tuple[float, float]:
    """Return (mean, std) or (0, 0) for empty."""
    if not vals:
        return 0.0, 0.0
    a = np.array(vals, dtype=float)
    return float(a.mean()), float(a.std())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _savefig(fig, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"creationDate": None})
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
# 1. total_snapshot_time.csv
# ---------------------------------------------------------------------------

def write_total_time_csv(runs: list[dict], outdir: str,
                         mem_sizes: list[int]):
    rows = []
    for mem in mem_sizes:
        row = {"mem_size_mib": mem}
        for mode in ("full", "live", "live_bpf"):
            vals = result_values(runs, "total_snapshot_ms",
                                 mem_size_mib=mem, mode=mode)
            mean, std = agg(vals)
            row[f"{mode}_ms"]     = round(mean, 2)
            row[f"{mode}_std_ms"] = round(std,  2)
        rows.append(row)

    path = os.path.join(outdir, "total_snapshot_time.csv")
    fields = ["mem_size_mib",
              "full_ms", "full_std_ms",
              "live_ms", "live_std_ms",
              "live_bpf_ms", "live_bpf_std_ms"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# 2. downtime_comparison.csv
# ---------------------------------------------------------------------------

def write_downtime_csv(runs: list[dict], outdir: str,
                       mem_sizes: list[int]):
    rows = []
    for mem in mem_sizes:
        row = {"mem_size_mib": mem}
        for mode in ("full", "live", "live_bpf"):
            vals = result_values(runs, "downtime_ms",
                                 mem_size_mib=mem, mode=mode)
            mean, std = agg(vals)
            row[f"{mode}_ms"]     = round(mean, 2)
            row[f"{mode}_std_ms"] = round(std,  2)
        rows.append(row)

    path = os.path.join(outdir, "downtime_comparison.csv")
    fields = ["mem_size_mib",
              "full_ms", "full_std_ms",
              "live_ms", "live_std_ms",
              "live_bpf_ms", "live_bpf_std_ms"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# 3. phase_breakdown.csv
# ---------------------------------------------------------------------------

def write_phase_breakdown_csv(runs: list[dict], outdir: str,
                              mem_sizes: list[int]):
    live_phases    = ["phase1", "populate_pages", "freeze", "stream", "finalize"]
    all_phase_keys = live_phases + ["create"]

    rows = []
    for mode in MODE_ORDER:
        for mem in mem_sizes:
            matched = select(runs, mode=mode, mem_size_mib=mem)
            if not matched:
                continue
            row = {"mode": mode, "mem_size_mib": mem}
            for pk in all_phase_keys:
                vals = [r["results"]["phase_breakdown_us"].get(pk, 0.0)
                        for r in matched]
                row[f"{pk}_us"] = round(float(np.mean(vals)), 1)
            rows.append(row)

    path = os.path.join(outdir, "phase_breakdown.csv")
    fields = ["mode", "mem_size_mib"] + [f"{pk}_us" for pk in all_phase_keys]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# 4. timeseries plots — 9 × (mem_size, mode)
# ---------------------------------------------------------------------------

def _load_timeseries(ts_path: str) -> list[dict]:
    rows = []
    with open(ts_path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "t_rel_s":    float(r["t_rel_s"]),
                    "throughput": float(r["throughput"]),
                    "avg_ms":     float(r.get("avg_ms",  0) or 0),
                    "p99_ms":     float(r.get("p99_ms",  0) or 0),
                    "p999_ms":    float(r.get("p999_ms", 0) or 0),
                    "failed":     int(r.get("failed",    0) or 0),
                })
            except (KeyError, ValueError):
                pass
    return rows


def plot_timeseries_grid(runs: list[dict], results_dir: str,
                         outdir: str, mem_sizes: list[int]):
    """One PNG per (mem_size, mode): throughput on left y-axis,
    avg latency and p99 on right y-axis."""
    for mem in mem_sizes:
        for mode in MODE_ORDER:
            # Pick the first iteration that has a timeseries file
            matched = [r for r in select(runs, mode=mode, mem_size_mib=mem)
                       if r["results"].get("timeseries_file")]
            if not matched:
                print(f"  SKIP timeseries: mode={mode} mem={mem} (no file)")
                continue
            run = matched[0]
            ts_rel = run["results"]["timeseries_file"]
            ts_path = os.path.join(results_dir, ts_rel)
            if not os.path.exists(ts_path):
                print(f"  SKIP timeseries: {ts_path} not found")
                continue

            ts_rows = _load_timeseries(ts_path)
            if not ts_rows:
                continue

            ok_rows   = [r for r in ts_rows if not r["failed"]]
            xs_ok     = [r["t_rel_s"]    for r in ok_rows]
            ys_ok     = [r["throughput"] for r in ok_rows]
            p99s      = [r["p99_ms"]     for r in ok_rows]
            avg_ms    = [r["avg_ms"]     for r in ok_rows]
            xs_all    = [r["t_rel_s"]    for r in ts_rows]
            ys_all    = [0.0 if r["failed"] else r["throughput"] for r in ts_rows]
            failed_xs = [r["t_rel_s"]    for r in ts_rows if r["failed"]]
            failed_ys = [0.0             for r in ts_rows if r["failed"]]

            fig, ax_thr = plt.subplots(figsize=(12, 6))
            ax_lat = ax_thr.twinx()

            # ── throughput (left) ────────────────────────────────────────
            ax_thr.scatter(xs_ok, ys_ok, s=4, color="steelblue",
                           alpha=0.4, label="throughput raw")
            if xs_all:
                _, ys_s = _rolling_mean(xs_all, ys_all, window_s=0.5)
                ax_thr.plot(xs_all, ys_s, color="steelblue",
                            linewidth=2, label="throughput (smoothed)")
            if failed_xs:
                ax_thr.scatter(failed_xs, failed_ys, s=40, color="firebrick",
                               marker="x", linewidths=1.5, zorder=5,
                               label="connection failed")

            # ── latency (right) ──────────────────────────────────────────
            if xs_ok:
                avg_sx, avg_sy   = _smooth_with_gaps(xs_ok, avg_ms, window_s=0.5)
                p99_sx,  p99_sy  = _smooth_with_gaps(xs_ok, p99s,  window_s=0.5)
                ax_lat.plot(avg_sx, avg_sy, color="forestgreen",
                            linewidth=2, linestyle="--", label="avg latency")
                ax_lat.plot(p99_sx, p99_sy, color="darkorange",
                            linewidth=2, linestyle=":",  label="p99 latency")
                ax_lat.scatter(xs_ok, avg_ms, s=4, color="forestgreen", alpha=0.3)
                ax_lat.scatter(xs_ok, p99s,   s=4, color="darkorange",  alpha=0.3)

            # ── snapshot / freeze markers ────────────────────────────────
            res = run["results"]
            snap_s   = res.get("ts_snap_start_s",  0)
            snap_e   = res.get("ts_snap_end_s",    0)
            freeze_s = res.get("ts_freeze_start_s", 0)
            freeze_e = res.get("ts_freeze_end_s",   0)

            if snap_s and snap_e:
                for ax in (ax_thr, ax_lat):
                    ax.axvline(snap_s, color="steelblue", linestyle="--",
                               linewidth=1, alpha=0.7)
                    ax.axvline(snap_e, color="steelblue", linestyle="--",
                               linewidth=1, alpha=0.7)
                if mode == "full":
                    for ax in (ax_thr, ax_lat):
                        ax.axvspan(snap_s, snap_e, alpha=0.12, color="firebrick",
                                   hatch="//", label="_nolegend_")
                elif freeze_s and freeze_e and freeze_e > freeze_s:
                    for ax in (ax_thr, ax_lat):
                        ax.axvspan(freeze_s, freeze_e, alpha=0.15,
                                   color="firebrick", hatch="//",
                                   label="_nolegend_")

            # ── styling ──────────────────────────────────────────────────
            ax_thr.set_xlabel("Time (s)", fontsize=LABEL_FONTSIZE)
            ax_thr.set_ylabel("Throughput (ops/s)", fontsize=LABEL_FONTSIZE,
                               color="steelblue")
            ax_thr.tick_params(axis="y", labelcolor="steelblue",
                               labelsize=FONTSIZE)
            ax_thr.tick_params(axis="x", labelsize=FONTSIZE)
            ax_thr.set_ylim(bottom=0)
            ax_thr.grid(True, alpha=0.3)

            ax_lat.set_ylabel("Latency (ms)", fontsize=LABEL_FONTSIZE,
                              color="dimgray")
            ax_lat.tick_params(axis="y", labelcolor="dimgray",
                              labelsize=FONTSIZE)
            ax_lat.set_ylim(bottom=0)

            # Combined legend
            lines_thr, labels_thr = ax_thr.get_legend_handles_labels()
            lines_lat, labels_lat = ax_lat.get_legend_handles_labels()
            ax_thr.legend(lines_thr + lines_lat, labels_thr + labels_lat,
                          fontsize=LEGEND_FONTSIZE, loc="upper left")

            fig.suptitle(
                f"{MODE_LABELS[mode]} — {mem} MiB",
                fontsize=FONTSIZE + 2, fontweight="bold",
            )
            fig.tight_layout()

            fname = f"timeseries_{mem}mib_{mode}.png"
            _savefig(fig, os.path.join(outdir, fname))


# ---------------------------------------------------------------------------
# 5. throughput_during_snapshot.png
# ---------------------------------------------------------------------------

def plot_throughput_during_snapshot(runs: list[dict], outdir: str,
                                    mem_sizes: list[int]):
    """Grouped bar chart: baseline / full / live / live_bpf ops/s per mem size."""
    series = [
        ("baseline", "Baseline",      DEFAULT_COLORS[4]),   # mediumpurple
        ("full",     "Full (sync)",   DEFAULT_COLORS[2]),   # firebrick
        ("live",     "Live (UFFD)",   DEFAULT_COLORS[0]),   # steelblue
        ("live_bpf", "Live (eBPF)",   DEFAULT_COLORS[3]),   # forestgreen
    ]

    x = np.arange(len(mem_sizes))
    n_series = len(series)
    width = 0.7 / n_series

    fig, ax = plt.subplots(figsize=(10, 6))

    for si, (key, label, color) in enumerate(series):
        means, stds = [], []
        for mem in mem_sizes:
            if key == "baseline":
                # baseline is the same regardless of mode; average over all modes
                vals = []
                for mode in MODE_ORDER:
                    vals += result_values(runs, "throughput",
                                          mem_size_mib=mem, mode=mode)
                vals = [v["baseline_ops_s"] for r in select(runs, mem_size_mib=mem)
                        if (v := r["results"].get("throughput"))]
            else:
                vals = [r["results"]["throughput"]["during_ops_s"]
                        for r in select(runs, mode=key, mem_size_mib=mem)
                        if r["results"].get("throughput")]
            mean, std = agg(vals)
            means.append(mean)
            stds.append(std)

        offset = (si - (n_series - 1) / 2) * width
        ax.bar(x + offset, means, width=width, label=label,
               color=color, yerr=stds, capsize=3)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{m} MiB" for m in mem_sizes], fontsize=FONTSIZE)
    ax.tick_params(axis="y", labelsize=FONTSIZE)
    ax.set_ylabel("Avg Throughput During Snapshot (ops/s)", fontsize=LABEL_FONTSIZE)
    ax.legend(fontsize=LEGEND_FONTSIZE)
    ax.set_ylim(bottom=0)
    ax.set_axisbelow(True)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()

    _savefig(fig, os.path.join(outdir, "throughput_during_snapshot.png"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Plot Firecracker snapshot benchmark JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("json", help="Path to snapshot_benchmark_<workload>.json")
    ap.add_argument("--outdir", default="figures",
                    help="Output directory for plots and CSVs")
    ap.add_argument("--mem-sizes", type=int, nargs="+",
                    default=[2048, 4096, 8192], metavar="MiB")
    args = ap.parse_args()

    runs = load_runs(args.json)
    if not runs:
        print("ERROR: no records in JSON", file=sys.stderr)
        sys.exit(1)

    # results/timeseries/ lives next to the JSON
    results_dir = os.path.dirname(os.path.abspath(args.json))

    os.makedirs(args.outdir, exist_ok=True)
    print(f"Loaded {len(runs)} records from {args.json}")
    print(f"Output → {args.outdir}/\n")

    print("Writing CSVs...")
    write_total_time_csv(runs, args.outdir, args.mem_sizes)
    write_downtime_csv(runs, args.outdir, args.mem_sizes)
    write_phase_breakdown_csv(runs, args.outdir, args.mem_sizes)

    print("\nPlotting timeseries...")
    plot_timeseries_grid(runs, results_dir, args.outdir, args.mem_sizes)

    print("\nPlotting throughput during snapshot...")
    plot_throughput_during_snapshot(runs, args.outdir, args.mem_sizes)

    print("\nDone.")


if __name__ == "__main__":
    main()
