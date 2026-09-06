#!/bin/bash
# Garbage collection plot script (Table 5 and the dirty-tracking results
# in Section 6.4)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results/gc"
FIGURES_PATH="$BASE_DIR/figures"

. "$BASE_DIR/eval/lib.sh"

mkdir -p "$FIGURES_PATH"

# Plot whichever halves were run: run.sh narrows to one of them via the
# COMPACTION and TRACKING variables, and a missing half is not an error.
shopt -s nullglob
CLASS_B=("$RESULTS_PATH"/gc_benchmark_classB_*.json)
CLASS_A=("$RESULTS_PATH"/gc_benchmark_classA_*.json)
shopt -u nullglob

if [[ ${#CLASS_B[@]} -eq 0 && ${#CLASS_A[@]} -eq 0 ]]; then
	die "No GC results in $RESULTS_PATH"
fi

progress_init "gc plots" \
	$(( (${#CLASS_B[@]} > 0) + (${#CLASS_A[@]} > 0) )) \
	"$BASE_DIR/results/logs/plot-gc.log"

TABLES=""

# Table 5: Compressor concurrent compaction (runtime and mean GC pause)
if [[ ${#CLASS_B[@]} -gt 0 ]]; then
	progress_step "concurrent compaction table"
	quiet python3 "$BASE_DIR/bench/print_gc_table.py" \
		-r "$RESULTS_PATH" -o "$FIGURES_PATH/gc_table.tex"
	TABLES="gc_table.tex"
fi

# GenImmix dirty tracking. The paper quotes these in the text of the
# garbage collection evaluation rather than as a numbered table.
if [[ ${#CLASS_A[@]} -gt 0 ]]; then
	progress_step "dirty tracking table"
	quiet python3 "$BASE_DIR/bench/print_gc_dirty_table.py" \
		-r "$RESULTS_PATH" -o "$FIGURES_PATH/gc_dirty_table.tex"
	TABLES="${TABLES:+$TABLES, }gc_dirty_table.tex"
fi

progress_done "tables: $TABLES"
