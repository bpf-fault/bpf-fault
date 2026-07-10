#!/bin/bash
# Dynamic linking plot script (Figure 10)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
FIGURES_PATH="$BASE_DIR/figures"

mkdir -p "$FIGURES_PATH"

python3 "$BASE_DIR/bench/plot_dynlink_micro.py" \
	-o "$FIGURES_PATH/figure10a.pdf"

python3 "$BASE_DIR/bench/plot_dynlink_steady.py" \
	-o "$FIGURES_PATH/figure10b.pdf"

python3 "$BASE_DIR/bench/plot_dynlink_startup.py" \
	-o "$FIGURES_PATH/figure10c.pdf" \
	-m "$FIGURES_PATH/dynlink_startup_mem.pdf"

echo "Figures saved to $FIGURES_PATH"
