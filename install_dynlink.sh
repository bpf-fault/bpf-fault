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
# clang-19: BPF arena address-space casts require clang >= 19.
# gawk, bison, python3, texinfo, gettext: libc dependencies.
# patchelf: required to modify the dynamic linker path of test executables.
# nodejs, docker: experiment dependencies.
# unzip: required by the Deno installer.
sudo apt-get install -y gawk bison python3 texinfo gettext clang-19 patchelf \
			nodejs docker.io unzip

echo "Installing Deno..."
if ! command -v deno &> /dev/null; then
	curl -fsSL https://deno.land/install.sh | sudo DENO_INSTALL=/usr/local sh -s -- --yes
fi

echo "Installing Google Chrome..."
if [[ ! -f /opt/google/chrome/chrome ]]; then
	curl -fsSL -o /tmp/google-chrome-stable_current_amd64.deb \
		https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
	sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb
	rm /tmp/google-chrome-stable_current_amd64.deb
fi

cd "$DYNLINK_PATH"
if [[ ! -e "README.md" ]]; then
	git submodule update --init
fi

echo "Building glibc..."
sudo bash glibc/compile_glibc.sh

echo "Building BPF fault handler..."
make -C fault_handler
