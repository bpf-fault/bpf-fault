# Shared helpers for the Firecracker snapshot plot scripts
# (plot_snapshot_timeseries.py, plot_snapshot_throughput.py).

import csv
import json
import os

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

FONTSIZE        = 16
LABEL_FONTSIZE  = 18
LEGEND_FONTSIZE = 14

# Throughput display scale: divide raw ops/s by this and use _OPS_UNIT as label
_OPS_SCALE = 1e6
_OPS_UNIT  = "M ops/s"


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


def mem_label(mem_mib: int) -> str:
    """Human-readable memory size label: 4096 -> '4 GB'."""
    if mem_mib % 1024 == 0:
        return f"{mem_mib // 1024} GB"
    return f"{mem_mib} MiB"


def detect_mem_sizes(runs: list[dict]) -> list[int]:
    mem_sizes = set()
    for run in runs:
        try:
            mem_size = int(run.get("config", {}).get("mem_size_mib"))
        except (TypeError, ValueError):
            continue
        mem_sizes.add(mem_size)
    return sorted(mem_sizes)


# ---------------------------------------------------------------------------
# Figure/timeseries helpers
# ---------------------------------------------------------------------------

def _savefig(fig, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"creationDate": None})
    plt.close(fig)
    print(f"  Saved: {path}")


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


def _compute_global_limits(runs: list[dict],
                            results_dir: str) -> tuple[float, float]:
    """Scan all referenced timeseries CSVs to compute global y-axis limits.

    Returns (max_throughput_ops_s, max_lat_p99_ms) across all non-failed
    samples in all runs, so every timeseries plot uses the same scale.
    """
    max_thr = 0.0
    max_lat = 0.0
    for run in runs:
        ts_rel = run["results"].get("timeseries_file")
        if not ts_rel:
            continue
        ts_path = os.path.join(results_dir, ts_rel)
        if not os.path.exists(ts_path):
            continue
        rows = _load_timeseries(ts_path)
        ok = [r for r in rows if not r["failed"]]
        if ok:
            max_thr = max(max_thr, max(r["throughput"] for r in ok))
            max_lat = max(max_lat, max(r["p99_ms"]     for r in ok))
    return max_thr, max_lat
