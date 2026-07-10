#!/bin/bash
# Fault-handling overhead breakdown plot script
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

mkdir -p "$FIGURES_PATH"

python3 "$BASE_DIR/bench/plot_overhead.py" \
	-i "$RESULTS_PATH/overhead.csv" \
	-o "$FIGURES_PATH/overhead_breakdown.pdf"

python3 "$BASE_DIR/bench/plot_overhead_baseline.py" \
	-i "$RESULTS_PATH/overhead_baseline.csv" \
	-o "$FIGURES_PATH/overhead_baseline.pdf"

python3 "$BASE_DIR/bench/plot_overhead_bpf.py" \
	-i "$RESULTS_PATH/overhead_bpf.csv" \
	-o "$FIGURES_PATH/overhead_bpf.pdf"

echo "Figures saved to $FIGURES_PATH"
