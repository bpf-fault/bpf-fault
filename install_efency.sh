#!/bin/bash
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
EFENCY_PATH="$BASE_DIR/efency"

echo "Installing efency dependencies..."
sudo apt-get update
# clang-19: BPF arena address-space casts require clang >= 19.
# ripgrep, python3, and jq are required by the efency experiment scripts.
# electric-fence provides /usr/lib/libefence.so, the efence baseline mode.
sudo apt-get install -y clang-19 ripgrep python3 jq electric-fence

cd "$EFENCY_PATH"
if [[ ! -e "Makefile" ]]; then
	git submodule update --init
fi

echo "Building efency..."
make -j
make ebpf -j
