#!/bin/bash
# Dynamic linking plot script (Figure 10)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

mkdir -p "$FIGURES_PATH"

progress_init "dynlink plots" 3 "$BASE_DIR/results/logs/plot-dynlink.log"

progress_step "figure10a"
quiet python3 "$BASE_DIR/bench/plot_dynlink_micro.py" \
	-o "$FIGURES_PATH/figure10a.pdf"

progress_step "figure10b"
quiet python3 "$BASE_DIR/bench/plot_dynlink_steady.py" \
	-o "$FIGURES_PATH/figure10b.pdf"

progress_step "figure10c"
quiet python3 "$BASE_DIR/bench/plot_dynlink_startup.py" \
	-o "$FIGURES_PATH/figure10c.pdf"

progress_done "figures: figure10a.pdf, figure10b.pdf, figure10c.pdf"
