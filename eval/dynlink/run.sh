#!/bin/bash
# Dynamic linking run script (Figure 10)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
DYNLINK_PATH="$BASE_DIR/bpf-dynlink"
RESULTS_PATH="$BASE_DIR/results/dynlink"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

mkdir -p "$RESULTS_PATH"

# One step per (workload, mode) unit; iteration counts are set per
# benchmark suite in run_dynlink_bench.py. The runner reuses existing
# results and only runs configurations missing from the results file.
progress_init "dynlink" 95 "$BASE_DIR/results/logs/run-dynlink.log"

sudo python3 -u "$DYNLINK_PATH/test_e2e/bench/run_dynlink_bench.py" \
	--results-file "$RESULTS_PATH/dynlink_results.json" 2>&1 \
	| filter_progress '^Running ' 's/^Running //'

progress_done
