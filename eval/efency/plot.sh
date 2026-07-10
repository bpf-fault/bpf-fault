#!/bin/bash
# efency benchmarks plot script (Figure 11)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results/efency"
FIGURES_PATH="$BASE_DIR/figures"

mkdir -p "$FIGURES_PATH"

python3 "$BASE_DIR/bench/plot_efency_fork.py" \
	-i "$RESULTS_PATH/fork_results.json" \
	-o "$FIGURES_PATH/efency_fork.pdf"

python3 "$BASE_DIR/bench/plot_efency_apps.py" \
	-i "$RESULTS_PATH/app_results.json" \
	-o "$FIGURES_PATH/efency_apps.pdf"

python3 "$BASE_DIR/bench/plot_efency_throughput.py" \
	-i "$RESULTS_PATH/malloc_results.json" \
	--apps-input "$RESULTS_PATH/app_results.json" \
	--output-micro "$FIGURES_PATH/figure11a.pdf" \
	--output-apps "$FIGURES_PATH/figure11b.pdf"

echo "Figures saved to $FIGURES_PATH"
