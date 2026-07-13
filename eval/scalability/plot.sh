#!/bin/bash
# Fault-handling scalability plot script (Figures 3b and 7)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

mkdir -p "$FIGURES_PATH"

progress_init "scalability plots" 2 "$RESULTS_PATH/logs/plot-scalability.log"

progress_step "figure3b"
quiet python3 "$BASE_DIR/bench/plot_scale.py" \
	-i "$RESULTS_PATH/scale_results.json" \
	-o "$FIGURES_PATH/figure3b.pdf"

progress_step "figure7"
quiet python3 "$BASE_DIR/bench/plot_scale_eval.py" \
	-i "$RESULTS_PATH/scale_results.json" \
	-o "$FIGURES_PATH/figure7.pdf"

progress_done "figures: figure3b.pdf, figure7.pdf"
