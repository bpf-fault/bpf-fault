#!/bin/bash
set -eu -o pipefail

if ! uname -r | grep -q "bpf-fault"; then
	echo "This script is intended to be run on a bpf_fault kernel."
	echo "Please switch to the bpf_fault kernel and try again."
	exit 1
fi

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
DYNLINK_PATH="$BASE_DIR/bpf-dynlink"

echo "Installing bpf-dynlink dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential gawk bison python3 texinfo gettext \
			clang lld patchelf libelf-dev zlib1g-dev nodejs \
			docker.io

cd "$DYNLINK_PATH"
if [[ ! -e "README.md" ]]; then
	git submodule update --init
fi

echo "Building patched glibc (this takes a while)..."
sudo bash glibc/compile_glibc.sh

echo "Building BPF fault handler..."
# The fault_handler Makefile defaults to clang-19; fall back to unversioned clang
make -C fault_handler CLANG="$(command -v clang-19 || command -v clang)"

echo "Installing Deno..."
if command -v deno &> /dev/null; then
	echo "Deno already installed: $(command -v deno)"
else
	curl -fsSL https://deno.land/install.sh | sudo DENO_INSTALL=/usr/local sh -s -- --yes
fi

echo "Installing Google Chrome..."
if [[ -f /opt/google/chrome/chrome ]]; then
	echo "Chrome already installed."
else
	curl -fsSL -o /tmp/google-chrome-stable_current_amd64.deb \
		https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
	sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb
	rm /tmp/google-chrome-stable_current_amd64.deb
fi

echo "bpf-dynlink built:"
ls -l "$DYNLINK_PATH"/fault_handler/bpf_reloc_loader "$DYNLINK_PATH"/glibc/build/install/lib/ld-linux-x86-64.so.2
