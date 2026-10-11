#!/bin/bash
# QEMU snapshot plot script (Table 4)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

WORKLOAD="${WORKLOAD:-redis_heavy}"

mkdir -p "$FIGURES_PATH"

QEMU_JSON="$RESULTS_PATH/snapshot_benchmark_qemu_$WORKLOAD.json"
if [[ ! -e "$QEMU_JSON" ]]; then
	die "No QEMU snapshot results at $QEMU_JSON"
fi

progress_init "snapshot-qemu plots" 1 \
	"$RESULTS_PATH/logs/plot-snapshot-qemu.log"

# Table 4: QEMU snapshot modes (total time, downtime, worst latency)
progress_step "qemu snapshot mode table"
quiet python3 "$BASE_DIR/bench/print_qemu_snapshot_table.py" \
	-r "$RESULTS_PATH" -w "$WORKLOAD" \
	-o "$FIGURES_PATH/qemu_snapshot_table.tex"

progress_done "tables: qemu_snapshot_table.tex"
