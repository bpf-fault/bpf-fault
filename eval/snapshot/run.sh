#!/bin/bash
# Firecracker snapshot run script (Figures 8 and 9)
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
FC_PATH="$BASE_DIR/firecracker"

# Workloads: redis_light redis_heavy redis_mixed memcached_light
#            memcached_heavy stream
# Figure 8 uses redis_heavy; Figure 9 uses redis_heavy and memcached_heavy
WORKLOADS="${WORKLOADS:-redis_heavy memcached_heavy}"
ITERATIONS="${ITERATIONS:-3}"
MEM_SIZES="${MEM_SIZES:-4096 8192}"

mkdir -p "$BASE_DIR/results"

cd "$FC_PATH"
for wl in $WORKLOADS; do
	echo "Running snapshot benchmark: $wl..."
	python3 tests/integration_tests/functional/run_snapshot_benchmark.py \
		--workload "$wl" \
		--iterations "$ITERATIONS" \
		--mem-sizes $MEM_SIZES \
		--bench-dir "$BASE_DIR"
done

echo "Results saved to $BASE_DIR/results/snapshot_benchmark_*.json"
