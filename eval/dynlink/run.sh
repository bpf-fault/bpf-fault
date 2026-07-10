#!/bin/bash
# Dynamic linking run script (Figure 10)
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
DYNLINK_PATH="$BASE_DIR/bpf-dynlink"
RESULTS_PATH="$BASE_DIR/results/dynlink"

ITERATIONS="${ITERATIONS:-20}"

mkdir -p "$RESULTS_PATH"

cd "$DYNLINK_PATH"
sudo bash test_e2e/run_all_benchmarks.sh

# Node and Docker workloads are not part of run_all_benchmarks.sh
echo "Running Node workloads..."
sudo bash test_e2e/benchmark_node.sh "$ITERATIONS"

echo "Running Docker workloads..."
sudo bash test_e2e/benchmark_docker.sh "$ITERATIONS"

cp "$DYNLINK_PATH"/test_e2e/results/* "$RESULTS_PATH/"
echo "Results saved to $RESULTS_PATH"
