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
# nodejs: experiment dependency.
# unzip: required by the Deno installer.
sudo apt-get install -y gawk bison python3 texinfo gettext clang-19 patchelf \
			nodejs unzip

echo "Installing Deno..."
if ! command -v deno &> /dev/null; then
	curl -fsSL https://deno.land/install.sh | sudo DENO_INSTALL=/usr/local sh -s -- --yes
fi

echo "Installing docker CLI..."
# docker.io >= 29.x links the docker CLI with Go's internal linker, which
# emits no DT_RELACOUNT tag; without it, glibc's relative-relocation
# batch path (and thus BPF deferral) never engages. Extract the CLI from
# the last externally linked build instead of using the system docker.
if [[ ! -f /usr/local/bin/docker-bench ]]; then
	DOCKER_DEB_URL="https://launchpad.net/ubuntu/+archive/primary/+files/docker.io_28.2.2-0ubuntu1_amd64.deb"
	DOCKER_TMP=$(mktemp -d)
	curl -fsSL -o "$DOCKER_TMP/docker.deb" "$DOCKER_DEB_URL"
	dpkg-deb -x "$DOCKER_TMP/docker.deb" "$DOCKER_TMP/extract"
	sudo install -m 755 "$DOCKER_TMP/extract/usr/bin/docker" /usr/local/bin/docker-bench
	rm -rf "$DOCKER_TMP"
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
