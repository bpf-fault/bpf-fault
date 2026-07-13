#!/bin/bash
# Page fault latency run script (Figure 3a and Table 3)
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
BENCH_PATH="$BASE_DIR/linux/tools/testing/selftests/bpf/bench_fault"
RESULTS_PATH="$BASE_DIR/results"

ITERATIONS="${ITERATIONS:-3}"
PAGES="${PAGES:-1024}"

mkdir -p "$RESULTS_PATH"

make -C "$BENCH_PATH" -j"$(nproc)"

# The runner reuses existing results and only runs configs missing from
# the results file.
sudo python3 "$BENCH_PATH/run_bench_fault.py" \
	-n "$PAGES" \
	--iterations "$ITERATIONS" \
	--results-file "$RESULTS_PATH/fault_results.json"

echo "Results saved to $RESULTS_PATH/fault_results.json"
