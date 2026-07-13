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

mkdir -p "$RESULTS_PATH"

# Iteration counts are set per benchmark in run_all_benchmarks.sh
cd "$DYNLINK_PATH"
sudo RESULTS_DIR="$RESULTS_PATH" bash test_e2e/run_all_benchmarks.sh

echo "Results saved to $RESULTS_PATH"
