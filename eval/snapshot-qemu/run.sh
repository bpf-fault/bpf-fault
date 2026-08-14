#!/bin/bash
# QEMU snapshot run script (QEMU columns of Figure 9 and the snapshot
# completion time discussion)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
QEMU_PATH="$BASE_DIR/qemu"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

if [[ ! -x "$QEMU_PATH/build/qemu-system-x86_64" ]]; then
	die "qemu-system-x86_64 not built. Run ./install_qemu.sh first."
fi

# Workloads: redis_light redis_mixed redis_heavy memcached_light
#            memcached_heavy
WORKLOADS="${WORKLOADS:-redis_heavy memcached_heavy}"
ITERATIONS="${ITERATIONS:-3}"
MEM_SIZES="${MEM_SIZES:-4096 8192}"
# full migrate live live_bpf; the migrate baseline runs up to its 120s
# non-convergence timeout per configuration under write-heavy load.
MODES="${MODES:-full migrate live live_bpf}"

mkdir -p "$BASE_DIR/results"

set -- $WORKLOADS; NW=$#
set -- $MEM_SIZES; NM=$#
set -- $MODES;     NMO=$#
TOTAL=$((NW * NMO * NM * ITERATIONS))
progress_init "snapshot-qemu" "$TOTAL" "$BASE_DIR/results/logs/run-snapshot-qemu.log"

# The benchmark writes its records and timeseries directly into
# results/ and only runs configurations missing from them.
sudo python3 -u "$QEMU_PATH/tests/bpf-fault-bench/run_snapshot_bench.py" \
	--workloads $WORKLOADS \
	--modes $MODES \
	--iterations "$ITERATIONS" \
	--mem-sizes $MEM_SIZES \
	--migrate-timeout "${MIGRATE_TIMEOUT:-120}" \
	--scratch-dir "$BASE_DIR/results/.qemu-scratch" \
	--results-dir "$BASE_DIR/results" 2>&1 \
	| filter_progress 'Running config: ' 's/.*Running config: //'

progress_done
