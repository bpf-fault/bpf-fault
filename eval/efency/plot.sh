#!/bin/bash
# efency benchmarks plot script (Figure 11)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results/efency"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

mkdir -p "$FIGURES_PATH"

progress_init "efency plots" 1 "$BASE_DIR/results/logs/plot-efency.log"

progress_step "figure11a, figure11b"
quiet python3 "$BASE_DIR/bench/plot_efency_throughput.py" \
	-i "$RESULTS_PATH/malloc_results.json" \
	--apps-input "$RESULTS_PATH/app_results.json" \
	--output-micro "$FIGURES_PATH/figure11a.pdf" \
	--output-apps "$FIGURES_PATH/figure11b.pdf"

progress_done "figures: figure11a.pdf, figure11b.pdf"
