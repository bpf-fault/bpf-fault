#!/bin/bash
# efency benchmarks run script (Figure 11)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
EFENCY_PATH="$BASE_DIR/efency"
RESULTS_PATH="$BASE_DIR/results/efency"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

ITERATIONS="${ITERATIONS:-3}"

mkdir -p "$RESULTS_PATH"

# Steps: build + malloc (5 modes) + apps (4 modes x 5 apps), per iteration
TOTAL=$((1 + 5 * ITERATIONS + 4 * 5 * ITERATIONS))
progress_init "efency" "$TOTAL" "$BASE_DIR/results/logs/run-efency.log"

cd "$EFENCY_PATH"

# ebpfency (the bpf_fault mode) is required for both figures, so a failed
# BPF build must abort rather than silently skip it.
progress_step "building (make, make ebpf, make bench)"
quiet make
quiet make ebpf
quiet make bench

# Figure 11a: malloc microbenchmarks, all modes (glibc is the baseline)
sudo python3 -u bench/run_malloc_bench.py \
	-m glibc efence efency_sigbus efency_handler ebpfency \
	-r "$ITERATIONS" \
	-o "$RESULTS_PATH/malloc_results.json" 2>&1 \
	| filter_progress '^Running .* round' \
		's/^Running (.*) round ([0-9]+\/[0-9]+)\.*$/malloc benchmark — \1 round \2/'

# Figure 11b: application benchmarks. Electric Fence is excluded: it
# crashes on most of these applications.
sudo python3 -u bench/run_app_bench.py \
	-m glibc efency_sigbus efency_handler ebpfency \
	--apps clang ripgrep git_status python jq \
	-r "$ITERATIONS" \
	-o "$RESULTS_PATH/app_results.json" 2>&1 \
	| filter_progress '^Running .* round' \
		's/^Running (.*) round ([0-9]+\/[0-9]+)\.*$/app benchmark — \1 round \2/'

progress_done
