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

# The devtool test runner needs the docker socket. Group membership from
# install_firecracker.sh only binds at login, so shells older than that
# install (or screen sessions) may lack it; re-exec under the docker
# group once before concluding docker is actually broken.
if ! timeout 10 docker ps &> /dev/null; then
	if [ "${_SNAPSHOT_REEXECED:-0}" = 1 ]; then
		die "Docker is inaccessible. Check the daemon (systemctl status docker)"$'\n'"and that $USER is in the docker group, then log out and back in."
	fi
	exec sg docker -c "$(printf '%q ' env _SNAPSHOT_REEXECED=1 "$SCRIPT_PATH" "$@")"
fi

# Workloads: redis_light redis_heavy redis_mixed memcached_light
#            memcached_heavy stream
# Figure 8 uses redis_heavy; Figure 9 uses redis_heavy and memcached_heavy
WORKLOADS="${WORKLOADS:-redis_heavy memcached_heavy}"
ITERATIONS="${ITERATIONS:-3}"
MEM_SIZES="${MEM_SIZES:-4096 8192}"

mkdir -p "$BASE_DIR/results"

# One step per configuration: 3 snapshot modes per (workload, memory
# size, iteration). The runner reuses existing results and only runs
# configurations missing from them.
set -- $WORKLOADS
NW=$#
set -- $MEM_SIZES
NM=$#
TOTAL=$((NW * 3 * NM * ITERATIONS))
progress_init "snapshot" "$TOTAL" "$BASE_DIR/results/logs/run-snapshot.log"

cd "$FC_PATH"
for wl in $WORKLOADS; do
	python3 -u tests/integration_tests/functional/run_snapshot_benchmark.py \
		--workload "$wl" \
		--iterations "$ITERATIONS" \
		--mem-sizes $MEM_SIZES \
		--bench-dir "$BASE_DIR" 2>&1 \
		| filter_progress \
			-M '^Running mode=|Installing build tools|Building version=|test session starts' \
			"s/^Running mode=([a-z_]+).*/$wl — preparing \\1 mode test container/; s/.*Installing build tools.*/$wl — preparing test container (build tools)/; s/^.*Building version=.*/$wl — building firecracker/; s/.*test session starts.*/$wl — collecting tests/" \
			'^Running config: ' 's/^Running config: //'
done

progress_done
