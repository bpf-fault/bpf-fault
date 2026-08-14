#!/usr/bin/env python3
# Generate the LaTeX table of QEMU snapshot modes (total time, downtime,
# worst request latency) from the QEMU snapshot benchmark results.
#
# Usage:
#   ./print_qemu_snapshot_table.py
#   ./print_qemu_snapshot_table.py -w redis_heavy -o ../figures/qemu_table.tex

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RESULTS = os.path.join(SCRIPT_DIR, "../results")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/qemu_snapshot_table.tex")

MODE_ORDER = ["full", "migrate", "live", "live_bpf"]
MODE_LABELS = {
    "full":     r"Synchronous (\texttt{savevm})",
    "migrate":  "Dirty tracking",
    "live":     r"Background (\uffd)",
    "live_bpf": r"Background (\name)",
}
MEMS = [8192, 16384]

# Worst request latency: max p99.9 over the snapshot window plus a
# post-completion grace period, so a stop-copy stall whose latency is
# reported by the first post-resume sample is attributed to the mode.
POST_GRACE_S = 0.5


def worst_latency_ms(results_dir, res):
    ts = res.get("timeseries_file")
    if not ts:
        return None
    path = os.path.join(results_dir, ts)
    if not os.path.isfile(path):
        return None
    lo = res.get("ts_snap_start_s", 0)
    hi = res.get("ts_snap_end_s", 0) + POST_GRACE_S
    worst = None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                t = float(row["t_rel_s"])
                if lo <= t <= hi:
                    worst = max(worst or 0.0, float(row["p999_ms"] or 0))
            except (KeyError, ValueError):
                pass
    return worst


def fmt_ms(ms):
    """Seconds with one decimal above 1s, otherwise whole milliseconds."""
    if ms >= 1000:
        return f"{ms / 1000:.1f}\\,s"
    return f"{ms:.0f}\\,ms"


def main():
    ap = argparse.ArgumentParser(
        description="Generate the QEMU snapshot-mode LaTeX table")
    ap.add_argument("-r", "--results-dir", default=DEFAULT_RESULTS)
    ap.add_argument("-w", "--workload", default="redis_heavy")
    ap.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    path = os.path.join(args.results_dir,
                        f"snapshot_benchmark_qemu_{args.workload}.json")
    if not os.path.isfile(path):
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        records = json.load(f)

    groups = defaultdict(list)
    for r in records:
        c = r["config"]
        groups[(c["mode"], c["mem_size_mib"])].append(r["results"])

    rows = []
    for mode in MODE_ORDER:
        row = {"label": MODE_LABELS[mode], "total": {}, "down": [],
               "worst": []}
        for mem in MEMS:
            entries = groups.get((mode, mem), [])
            if not entries:
                print(f"error: no records for mode={mode} mem={mem}",
                      file=sys.stderr)
                sys.exit(1)
            n = len(entries)
            row["total"][mem] = sum(e["total_snapshot_ms"]
                                    for e in entries) / n
            row["down"].append(sum(e["downtime_ms"] for e in entries) / n)
            worsts = [worst_latency_ms(args.results_dir, e)
                      for e in entries]
            worsts = [w for w in worsts if w is not None]
            if worsts:
                row["worst"].append(sum(worsts) / len(worsts))
        rows.append(row)

    def span(vals):
        lo, hi = min(vals), max(vals)
        if fmt_ms(lo) == fmt_ms(hi):
            return fmt_ms(lo)
        return f"{fmt_ms(lo).replace(chr(92) + ',ms', '')}--{fmt_ms(hi)}" \
            if hi < 1000 and lo < 1000 else f"{fmt_ms(lo)}--{fmt_ms(hi)}"

    # Plain-text summary to stderr
    hdr = (f"{'Mode':<24s} {'8GB total':>10s} {'16GB total':>11s}"
           f" {'downtime':>16s} {'worst lat':>16s}")
    print(hdr, file=sys.stderr)
    print("─" * len(hdr), file=sys.stderr)
    for r in rows:
        print(f"{r['label']:<24s} {r['total'][8192]:>8,.0f}ms"
              f" {r['total'][16384]:>9,.0f}ms {span(r['down']):>16s}"
              f" {span(r['worst']) if r['worst'] else '--':>16s}",
              file=sys.stderr)

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\footnotesize")
    lines.append(r"\begin{tabular}{l rr r r}")
    lines.append(r"\toprule")
    lines.append(r" & \multicolumn{2}{c}{\textbf{Total}} & & \\")
    lines.append(r"\cmidrule(lr){2-3}")
    lines.append(r"\textbf{Mode} & \textbf{8\,GB} & \textbf{16\,GB}"
                 r" & \textbf{Downtime} & \textbf{Worst lat.} \\")
    lines.append(r"\midrule")
    for r in rows:
        total8 = f"{r['total'][8192] / 1000:.2f}\\,s"
        total16 = f"{r['total'][16384] / 1000:.2f}\\,s"
        worst = span(r["worst"]) if r["worst"] else "--"
        lines.append(f"{r['label']} & {total8} & {total16}"
                     f" & {span(r['down'])} & {worst} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\caption{QEMU snapshot modes with Redis.}")
    lines.append(r"\vspace{-1em}")
    lines.append(r"\label{tab:qemu-snapshots}")
    lines.append(r"\end{table}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"LaTeX table written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
