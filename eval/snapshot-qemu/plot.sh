#!/bin/bash
# QEMU snapshot plot script (QEMU Figure 9 variants and timeline
# candidates)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

FIG_WORKLOAD="${FIG_WORKLOAD:-redis_heavy}"
FIG_MEM="${FIG_MEM:-8192}"

mkdir -p "$FIGURES_PATH"

QEMU_JSON="$RESULTS_PATH/snapshot_benchmark_qemu_$FIG_WORKLOAD.json"
if [[ ! -e "$QEMU_JSON" ]]; then
	die "No QEMU snapshot results at $QEMU_JSON"
fi

progress_init "snapshot-qemu plots" 2 \
	"$RESULTS_PATH/logs/plot-snapshot-qemu.log"

# Timeline plots per iteration (Figure 8-style panels for QEMU)
progress_step "timeline candidates ($FIG_WORKLOAD, ${FIG_MEM} MiB, per iteration)"
quiet python3 "$BASE_DIR/bench/plot_snapshot_timeseries.py" "$QEMU_JSON" \
	--mem "$FIG_MEM" \
	--outdir "$FIGURES_PATH/snapshot_timeseries_qemu_$FIG_WORKLOAD"

# Figure 9 with both hypervisors side by side
progress_step "figure9a_qemu, figure9b_qemu (FC + QEMU)"
quiet python3 "$BASE_DIR/bench/plot_snapshot_throughput.py" \
	--results-dir "$RESULTS_PATH" \
	--out-dir "$FIGURES_PATH" \
	--fc-mems 4096 8192 \
	--vmm both \
	--output-throughput figure9a_qemu.pdf \
	--output-latency figure9b_qemu.pdf

progress_done "figures: figure9a_qemu.pdf, figure9b_qemu.pdf, timelines in snapshot_timeseries_qemu_$FIG_WORKLOAD/"
