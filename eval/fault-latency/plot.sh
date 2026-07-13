#!/bin/bash
# Page fault latency plot script (Figure 3a and Table 3)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

mkdir -p "$FIGURES_PATH"

progress_init "fault-latency plots" 2 "$RESULTS_PATH/logs/plot-fault-latency.log"

progress_step "figure3a"
quiet python3 "$BASE_DIR/bench/plot_fault.py" \
	-i "$RESULTS_PATH/fault_results.json" \
	-o "$FIGURES_PATH/figure3a.pdf"

progress_step "table3"
quiet python3 "$BASE_DIR/bench/print_latency_table.py" \
	-i "$RESULTS_PATH/fault_results.json" \
	-o "$FIGURES_PATH/table3.tex"

progress_done "figures: figure3a.pdf, table3.tex"
