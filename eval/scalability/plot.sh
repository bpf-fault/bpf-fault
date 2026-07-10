#!/bin/bash
# Fault-handling scalability plot script (Figures 3b and 7)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

mkdir -p "$FIGURES_PATH"

python3 "$BASE_DIR/bench/plot_scale.py" \
	-i "$RESULTS_PATH/scale_results.json" \
	-o "$FIGURES_PATH/figure3b.pdf"

python3 "$BASE_DIR/bench/plot_scale_eval.py" \
	-i "$RESULTS_PATH/scale_results.json" \
	-o "$FIGURES_PATH/figure7.pdf"

echo "Figures saved to $FIGURES_PATH"
