#!/bin/bash
# efency benchmarks run script (Figure 11)
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
EFENCY_PATH="$BASE_DIR/efency"
RESULTS_PATH="$BASE_DIR/results/efency"

ITERATIONS="${ITERATIONS:-3}"

mkdir -p "$RESULTS_PATH"

cd "$EFENCY_PATH"

echo "Building efency..."
# ebpfency (the bpf_fault mode) is required for both figures, so a failed
# BPF build must abort rather than silently skip it.
make
make ebpf
make bench

# Figure 11a: malloc microbenchmarks, all modes (glibc is the baseline)
sudo python3 bench/run_malloc_bench.py \
	-m glibc efence efency_sigbus efency_handler ebpfency \
	-r "$ITERATIONS" \
	-o "$RESULTS_PATH/malloc_results.json"

# Figure 11b: application benchmarks. Electric Fence is excluded: it
# crashes on most of these applications.
sudo python3 bench/run_app_bench.py \
	-m glibc efency_sigbus efency_handler ebpfency \
	--apps clang ripgrep git_status python jq \
	-r "$ITERATIONS" \
	-o "$RESULTS_PATH/app_results.json"

echo "Results saved to $RESULTS_PATH"
