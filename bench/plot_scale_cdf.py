#!/usr/bin/env python3
# Plot CDF of per-thread completion times from scale benchmark results.
#
# Reads scale_results.json (same format as run_bench_scale.py output) and
# runs bench_fault_scale with -c to collect per-thread elapsed times.
#
# Usage:
#   ./plot_scale_cdf.py                          # defaults: 64 threads, 64 pages
#   ./plot_scale_cdf.py -t 128 -n 64 -r 5       # 128 threads, 5 rounds
#   ./plot_scale_cdf.py -o ../figures/cdf.pdf    # custom output

import argparse
import os
import sys
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bench_lib import run_cmd

# Embed fonts as TrueType so PDFs are editable in Illustrator/Inkscape
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BENCH = os.path.join(
    SCRIPT_DIR, "../linux/tools/testing/selftests/bpf/bench_fault/bench_fault_scale")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "../figures/scale_cdf.pdf")

MODE_LABELS = {
    "bpf": "bpf_fault",
    "uffd": "userfaultfd",
    "uffd_mt": "uffd (16 handlers)",
    "uffd_mt1": "uffd (1:1 handlers)",
}

MODE_COLORS = {
    "bpf": "forestgreen",
    "uffd": "darkorange",
    "uffd_mt": "goldenrod",
    "uffd_mt1": "mediumpurple",
}

MODE_LINESTYLES = {
    "bpf": "-",
    "uffd": "--",
    "uffd_mt": ":",
    "uffd_mt1": "-.",
}


def run_bench(bench_path, threads, pages_per_thread, mode):
    """Run bench_fault_scale with CDF mode and return per-thread elapsed_ns."""
    stdout = run_cmd([bench_path, "-t", str(threads), "-n", str(pages_per_thread),
                      "-b", mode, "-c"])
    if stdout is None:
        return None

    elapsed = []
    for line in stdout.strip().splitlines():
        if line.startswith("cdf "):
            for token in line.split():
                if token.startswith("elapsed_ns="):
                    elapsed.append(int(token.split("=", 1)[1]))
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="CDF of per-thread completion times (bpf vs uffd)")
    parser.add_argument("-t", "--threads", type=int, default=64,
                        help="Number of worker threads (default: 64)")
    parser.add_argument("-n", "--pages", type=int, default=64,
                        help="Pages per thread (default: 64)")
    parser.add_argument("-r", "--rounds", type=int, default=3,
                        help="Number of rounds to aggregate (default: 3)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="Output PDF file")
    parser.add_argument("-b", "--bench", default=DEFAULT_BENCH,
                        help="Path to bench_fault_scale binary")
    args = parser.parse_args()

    if not os.path.isfile(args.bench):
        print(f"error: {args.bench} not found, run 'make' first", file=sys.stderr)
        sys.exit(1)

    modes = ["bpf", "uffd", "uffd_mt", "uffd_mt1"]
    # mode -> list of all per-thread elapsed_ns across rounds
    data = defaultdict(list)

    for mode in modes:
        for r in range(args.rounds):
            print(f"  round {r+1}/{args.rounds}: {mode} "
                  f"threads={args.threads} pages={args.pages}",
                  file=sys.stderr)
            elapsed = run_bench(args.bench, args.threads, args.pages, mode)
            if elapsed:
                data[mode].extend(elapsed)

    if not data:
        print("error: no data collected", file=sys.stderr)
        sys.exit(1)

    # Plot CDF
    fig, ax = plt.subplots(figsize=(5, 3.5))

    for mode in modes:
        if mode not in data:
            continue
        values = np.array(sorted(data[mode])) / 1e3  # convert to us
        cdf = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, cdf,
                label=MODE_LABELS.get(mode, mode),
                color=MODE_COLORS.get(mode, None),
                linestyle=MODE_LINESTYLES.get(mode, "-"),
                linewidth=1.5)

    ax.set_xscale("log")
    ax.set_xlabel("Per-thread completion time (\u00b5s)", fontsize=11)
    ax.set_ylabel("CDF", fontsize=11)
    ax.set_ylim(0, 1.02)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    fig.savefig(args.output, dpi=300, metadata={"creationDate": None})
    plt.close(fig)
    print(f"Plot saved to {args.output}", file=sys.stderr)

    # Print summary stats
    for mode in modes:
        if mode not in data:
            continue
        values = np.array(data[mode]) / 1e3
        print(f"\n{MODE_LABELS.get(mode, mode)}:", file=sys.stderr)
        print(f"  median: {np.median(values):.1f} us", file=sys.stderr)
        print(f"  p99:    {np.percentile(values, 99):.1f} us", file=sys.stderr)
        print(f"  max:    {np.max(values):.1f} us", file=sys.stderr)
        print(f"  stdev:  {np.std(values):.1f} us", file=sys.stderr)


if __name__ == "__main__":
    main()
