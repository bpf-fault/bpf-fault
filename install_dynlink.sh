#!/bin/bash
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
DYNLINK_PATH="$BASE_DIR/bpf-dynlink"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# Prime sudo credentials before output is redirected to the log
sudo -v

install_deps() {
	sudo apt-get update
	# clang-19: BPF arena address-space casts require clang >= 19.
	# gawk, bison, python3, texinfo, gettext: libc dependencies.
	# patchelf: required to modify the dynamic linker path of test executables.
	# nodejs: experiment dependency.
	# unzip: required by the Deno installer.
	sudo apt-get install -y gawk bison python3 texinfo gettext clang-19 patchelf \
				nodejs unzip
}

install_deno() {
	curl -fsSL https://deno.land/install.sh | sudo DENO_INSTALL=/usr/local sh -s -- --yes
}

install_docker_cli() {
	# docker.io >= 29.x links the docker CLI with Go's internal linker,
	# which emits no DT_RELACOUNT tag; without it, glibc's
	# relative-relocation batch path (and thus BPF deferral) never
	# engages. Extract the CLI from the last externally linked build
	# instead of using the system docker.
	local DOCKER_DEB_URL="https://launchpad.net/ubuntu/+archive/primary/+files/docker.io_28.2.2-0ubuntu1_amd64.deb"
	local DOCKER_TMP
	DOCKER_TMP=$(mktemp -d)
	curl -fsSL -o "$DOCKER_TMP/docker.deb" "$DOCKER_DEB_URL"
	dpkg-deb -x "$DOCKER_TMP/docker.deb" "$DOCKER_TMP/extract"
	sudo install -m 755 "$DOCKER_TMP/extract/usr/bin/docker" /usr/local/bin/docker-bench
	rm -rf "$DOCKER_TMP"
}

install_chrome() {
	curl -fsSL -o /tmp/google-chrome-stable_current_amd64.deb \
		https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
	sudo apt-get install -y /tmp/google-chrome-stable_current_amd64.deb
	rm /tmp/google-chrome-stable_current_amd64.deb
}

checklist_init "install_dynlink" 7 "$BASE_DIR/results/logs/install-dynlink.log"

checklist_step "install dependencies" install_deps

if command -v deno &> /dev/null; then
	checklist_skip "install Deno" "already installed"
else
	checklist_step "install Deno" install_deno
fi

if [[ -f /usr/local/bin/docker-bench ]]; then
	checklist_skip "install docker CLI" "already installed"
else
	checklist_step "install docker CLI" install_docker_cli
fi

if [[ -f /opt/google/chrome/chrome ]]; then
	checklist_skip "install Google Chrome" "already installed"
else
	checklist_step "install Google Chrome" install_chrome
fi

if [[ -e "$DYNLINK_PATH/README.md" ]]; then
	checklist_skip "initialize bpf-dynlink submodule" "already checked out"
else
	checklist_step "initialize bpf-dynlink submodule" \
		git -C "$BASE_DIR" submodule update --init bpf-dynlink
fi

cd "$DYNLINK_PATH"
checklist_step "build glibc" sudo bash glibc/compile_glibc.sh
checklist_step "build BPF fault handler" make -C fault_handler

checklist_done
