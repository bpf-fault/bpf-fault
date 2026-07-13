#!/bin/bash
# Page fault latency plot script (Figure 3a and Table 3)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

mkdir -p "$FIGURES_PATH"

python3 "$BASE_DIR/bench/plot_fault.py" \
	-i "$RESULTS_PATH/fault_results.json" \
	-o "$FIGURES_PATH/figure3a.pdf"

python3 "$BASE_DIR/bench/print_latency_table.py" \
	-i "$RESULTS_PATH/fault_results.json" \
	-o "$FIGURES_PATH/table3.tex"

echo "Figures saved to $FIGURES_PATH"
