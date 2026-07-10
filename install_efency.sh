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
sudo apt-get install -y clang make libelf-dev

cd "$EFENCY_PATH"
if [[ ! -e "Makefile" ]]; then
	git submodule update --init
fi

# Download the original efence library for baseline comparisons
if [[ -x "scripts/download-efence.sh" ]]; then
	./scripts/download-efence.sh
fi

# efency's Makefile defaults to clang-19; fall back to unversioned clang
CLANG_BIN=$(command -v clang-19 || command -v clang)

echo "Building efency..."
make -j"$(nproc)"
make ebpf -j"$(nproc)" CLANG="$CLANG_BIN"

echo "efency built:"
ls -l "$EFENCY_PATH"/bin/*.so
