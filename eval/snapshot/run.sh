#!/bin/bash
# Firecracker snapshot run script (Figures 8 and 9)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
FC_PATH="$BASE_DIR/firecracker"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# Workloads: redis_light redis_heavy redis_mixed memcached_light
#            memcached_heavy stream
# Figure 8 uses redis_heavy; Figure 9 uses redis_heavy and memcached_heavy
WORKLOADS="${WORKLOADS:-redis_heavy memcached_heavy}"
ITERATIONS="${ITERATIONS:-3}"
MEM_SIZES="${MEM_SIZES:-4096 8192}"

mkdir -p "$BASE_DIR/results"

# One step per (workload, snapshot mode)
set -- $WORKLOADS
TOTAL=$(($# * 3))
progress_init "snapshot" "$TOTAL" "$BASE_DIR/results/logs/run-snapshot.log"

cd "$FC_PATH"
for wl in $WORKLOADS; do
	python3 -u tests/integration_tests/functional/run_snapshot_benchmark.py \
		--workload "$wl" \
		--iterations "$ITERATIONS" \
		--mem-sizes $MEM_SIZES \
		--bench-dir "$BASE_DIR" 2>&1 \
		| filter_progress '^Running mode=' \
			"s/^Running mode=([a-z_]+).*/$wl — \\1 snapshot mode/"
done

progress_done
