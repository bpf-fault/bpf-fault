#!/bin/bash
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

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

# setup_experiment.sh expects the fork's memtier_benchmark on PATH; run
# ./install_memtier.sh first.
./setup_experiment.sh "$@"

echo "Log out and log back in for user group changes to take effect."
