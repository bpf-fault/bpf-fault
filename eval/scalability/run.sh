#!/bin/bash
# Fault-handling scalability run script (Figures 3b and 7)
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
PAGES="${PAGES:-64}"
# Figure 3b uses baseline/uffd/uffd_mt/sigsegv; Figure 7 uses baseline/uffd/bpf
MODES="${MODES:-baseline,uffd,uffd_mt,sigsegv,bpf}"

mkdir -p "$RESULTS_PATH"

# One step per configuration: each mode runs 14 thread counts per
# iteration, plus the build.
NMODES=$(awk -F, '{print NF}' <<< "$MODES")
progress_init "scalability" $((1 + NMODES * 14 * ITERATIONS)) \
	"$RESULTS_PATH/logs/run-scalability.log"

progress_step "building bench_fault"
quiet make -C "$BENCH_PATH" -j"$(nproc)"

# The runner reuses existing results and only runs configs missing from
# the results file.
sudo python3 -u "$BENCH_PATH/run_bench_scale.py" \
	-n "$PAGES" \
	-m "$MODES" \
	--iterations "$ITERATIONS" \
	--results-file "$RESULTS_PATH/scale_results.json" 2>&1 \
	| filter_progress 'Progress:' \
		's/.*Progress: [0-9.]+% \(([0-9]+\/[0-9]+)\).*/scalability sweep — configuration \1/'

progress_done
