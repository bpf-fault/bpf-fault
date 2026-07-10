#!/bin/bash
set -eu -o pipefail

# Builds Firecracker, downloads the guest kernel and rootfs images, and
# builds the app rootfs. Arguments are forwarded to setup_experiment.sh
# (e.g. --skip-build, --skip-rootfs, --no-smoke-test).

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
FC_PATH="$BASE_DIR/firecracker"

cd "$FC_PATH"
if [[ ! -e "Cargo.toml" ]]; then
	git submodule update --init
fi

MEMTIER_SRC="$BASE_DIR/memtier_benchmark" \
BPFFAULT_DIR="$BASE_DIR" \
BENCH_DIR="$BASE_DIR/bench" \
BPF_VMLINUX="$BASE_DIR/linux/vmlinux" \
./setup_experiment.sh "$@"
