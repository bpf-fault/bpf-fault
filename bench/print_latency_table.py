#!/usr/bin/env python3
# Generate a LaTeX table of per-fault latency (avg and p99) for
# bpf_fault vs userfaultfd across fault types.
#
# Usage:
#   ./print_latency_table.py
#   ./print_latency_table.py -i ../results/fault_results.json
#   ./print_latency_table.py -o ../figures/latency_table.tex

import argparse
import os
import sys
from collections import defaultdict

from bench_lib import BenchResults, parse_results_file

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "../results/fault_results.json")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/latency_table.tex")

FAULT_ORDER = ["missing", "wp", "minor"]
FAULT_LABELS = {
    "missing": "Missing (anon)",
    "wp":      "Write-protect",
    "minor":   "Minor (shmem)",
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate LaTeX latency table (bpf vs uffd)")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                        help="Input JSON results file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output .tex file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    results = parse_results_file(args.input, BenchResults)

    # The reused results file can accumulate runs with different page
    # counts, which would get averaged together below.
    num_pages = {r.config.get("num_pages") for r in results}
    if len(num_pages) > 1:
        print(f"warning: results mix multiple num_pages values "
              f"({sorted(num_pages, key=str)}), averaging across them",
              file=sys.stderr)

    # Group by (fault_type, mode), using only write faults.
    # WP and minor are write-only; filtering missing to write-only
    # keeps the table consistent and matches the eval text.
    groups = defaultdict(list)
    for r in results:
        c = r.config
        if c.get("access", "write") != "write":
            continue
        key = (c.get("fault_type", ""), c.get("mode", ""))
        groups[key].append(r.results)

    # Collect data rows
    rows = []
    for ft in FAULT_ORDER:
        uffd_entries = groups.get((ft, "uffd"), [])
        bpf_entries = groups.get((ft, "bpf"), [])
        if not uffd_entries or not bpf_entries:
            continue

        n_u = len(uffd_entries)
        n_b = len(bpf_entries)
        uffd_avg = sum(e["latency_ns"]["avg"] for e in uffd_entries) / n_u
        uffd_p99 = sum(e["latency_ns"]["p99"] for e in uffd_entries) / n_u
        bpf_avg = sum(e["latency_ns"]["avg"] for e in bpf_entries) / n_b
        bpf_p99 = sum(e["latency_ns"]["p99"] for e in bpf_entries) / n_b
        speedup_avg = uffd_avg / bpf_avg
        speedup_p99 = uffd_p99 / bpf_p99

        rows.append({
            "label": FAULT_LABELS[ft],
            "uffd_avg": uffd_avg,
            "uffd_p99": uffd_p99,
            "bpf_avg": bpf_avg,
            "bpf_p99": bpf_p99,
            "speedup_avg": speedup_avg,
            "speedup_p99": speedup_p99,
        })

    # Print plain-text summary to stderr
    hdr = (f"{'Fault Type':<18s} {'uffd avg':>10s} {'uffd p99':>10s}"
           f" {'bpf avg':>10s} {'bpf p99':>10s}"
           f" {'Avg x':>7s} {'p99 x':>7s}")
    print(hdr, file=sys.stderr)
    print("─" * len(hdr), file=sys.stderr)
    for r in rows:
        print(f"{r['label']:<18s} {r['uffd_avg']:>10,.0f} {r['uffd_p99']:>10,.0f}"
              f" {r['bpf_avg']:>10,.0f} {r['bpf_p99']:>10,.0f}"
              f" {r['speedup_avg']:>6.1f}x {r['speedup_p99']:>6.1f}x",
              file=sys.stderr)

    # Generate LaTeX
    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\footnotesize")
    lines.append(r"\begin{tabular}{l rr rr}")
    lines.append(r"\toprule")
    lines.append(r" & \multicolumn{2}{c}{\uffd} & \multicolumn{2}{c}{\name} \\")
    lines.append(r"\cmidrule(lr){2-3} \cmidrule(lr){4-5}")
    lines.append(r"\textbf{Fault type} & \textbf{Avg} & \textbf{p99} & \textbf{Avg} & \textbf{p99} \\")
    lines.append(r"\midrule")
    for r in rows:
        lines.append(
            f"{r['label']:<18s} & {r['uffd_avg']/1000:>4.1f} & {r['uffd_p99']/1000:>4.1f}"
            f" & {r['bpf_avg']/1000:>3.1f} & {r['bpf_p99']/1000:>3.1f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"%\vspace{-0.5em}")
    lines.append(r"\caption{Per-fault write latency (\us) across fault types.}")
    lines.append(r"\vspace{-1em}")
    lines.append(r"\label{tab:fault-latency}")
    lines.append(r"\end{table}")

    tex = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(tex)
    print(f"LaTeX table written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
