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

# Extra arguments are forwarded to efency's run_all.sh (e.g. --skip-apps)
cd "$EFENCY_PATH"
sudo ./bench/run_all.sh -r "$ITERATIONS" "$@"

cp "$EFENCY_PATH"/results/*.json "$RESULTS_PATH/"
echo "Results saved to $RESULTS_PATH"
