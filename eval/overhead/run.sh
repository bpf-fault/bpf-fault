#!/bin/bash
# Fault-handling overhead breakdown run script
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
PAGES="${PAGES:-4096}"

mkdir -p "$RESULTS_PATH"

make -C "$BENCH_PATH" -j"$(nproc)"

cd "$BENCH_PATH"

echo "Running userfaultfd overhead breakdown..."
sudo ./bench_fault_overhead -k -C -n "$PAGES" -r "$ITERATIONS" \
	-o "$RESULTS_PATH/overhead.csv"

echo "Running baseline overhead breakdown..."
sudo ./bench_fault_overhead_baseline -k -C -n "$PAGES" -r "$ITERATIONS" \
	-o "$RESULTS_PATH/overhead_baseline.csv"

echo "Running bpf_fault overhead breakdown..."
sudo ./bench_fault_overhead_bpf -k -C -n "$PAGES" -r "$ITERATIONS" \
	-o "$RESULTS_PATH/overhead_bpf.csv"

echo "Results saved to $RESULTS_PATH/overhead{,_baseline,_bpf}.csv"
