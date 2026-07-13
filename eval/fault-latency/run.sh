#!/bin/bash
# Page fault latency run script (Figure 3a and Table 3)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
BENCH_PATH="$BASE_DIR/linux/tools/testing/selftests/bpf/bench_fault"
RESULTS_PATH="$BASE_DIR/results"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

ITERATIONS="${ITERATIONS:-3}"
PAGES="${PAGES:-1024}"

mkdir -p "$RESULTS_PATH"

# One step per configuration: 14 (fault type, mode, access) combinations
# per iteration, plus the build.
progress_init "fault-latency" $((1 + 14 * ITERATIONS)) \
	"$RESULTS_PATH/logs/run-fault-latency.log"

progress_step "building bench_fault"
quiet make -C "$BENCH_PATH" -j"$(nproc)"

# The runner reuses existing results and only runs configs missing from
# the results file.
sudo python3 -u "$BENCH_PATH/run_bench_fault.py" \
	-n "$PAGES" \
	--iterations "$ITERATIONS" \
	--results-file "$RESULTS_PATH/fault_results.json" 2>&1 \
	| filter_progress 'Progress:' \
		's/.*Progress: [0-9.]+% \(([0-9]+\/[0-9]+)\).*/fault latency sweep — configuration \1/'

progress_done
