#!/bin/bash
# Firecracker snapshot plot script (Figures 8 and 9)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

# Figure 8 panels are the timeseries plots for this workload and memory
# size; one plot is generated per iteration, and the paper panel is
# chosen from them by hand.
FIG8_WORKLOAD="${FIG8_WORKLOAD:-redis_heavy}"
FIG8_MEM="${FIG8_MEM:-8192}"

mkdir -p "$FIGURES_PATH"

FIG8_JSON="$RESULTS_PATH/snapshot_benchmark_$FIG8_WORKLOAD.json"
if [[ ! -e "$FIG8_JSON" ]]; then
	die "No snapshot results at $FIG8_JSON"
fi

progress_init "snapshot plots" 2 "$RESULTS_PATH/logs/plot-snapshot.log"

# Figure 8: Redis throughput and tail latency while taking a snapshot
progress_step "figure8 panel candidates ($FIG8_WORKLOAD, ${FIG8_MEM} MiB, per iteration)"
quiet python3 "$BASE_DIR/bench/plot_snapshot_timeseries.py" "$FIG8_JSON" \
	--mem "$FIG8_MEM" \
	--outdir "$FIGURES_PATH/snapshot_timeseries_$FIG8_WORKLOAD"

# Figure 9: throughput and latency while the VM runs with snapshot WP active
progress_step "figure9a, figure9b"
quiet python3 "$BASE_DIR/bench/plot_snapshot_throughput.py" \
	--results-dir "$RESULTS_PATH" \
	--out-dir "$FIGURES_PATH" \
	--fc-mems 4096 8192 \
	--output-throughput figure9a.pdf \
	--output-latency figure9b.pdf

progress_done "figures: figure9a.pdf, figure9b.pdf, figure8 candidates in snapshot_timeseries_$FIG8_WORKLOAD/"
