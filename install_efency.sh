#!/bin/bash
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
EFENCY_PATH="$BASE_DIR/efency"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# Prime sudo credentials before output is redirected to the log
sudo -v

install_deps() {
	sudo apt-get update
	# clang-19: BPF arena address-space casts require clang >= 19.
	# ripgrep, python3, and jq are required by the efency experiment scripts.
	# electric-fence provides /usr/lib/libefence.so, the efence baseline mode.
	sudo apt-get install -y clang-19 ripgrep python3 jq electric-fence
}

checklist_init "install_efency" 4 "$BASE_DIR/results/logs/install-efency.log"

checklist_step "install dependencies" install_deps

if [[ -e "$EFENCY_PATH/Makefile" ]]; then
	checklist_skip "initialize efency submodule" "already checked out"
else
	checklist_step "initialize efency submodule" \
		git -C "$BASE_DIR" submodule update --init efency
fi

cd "$EFENCY_PATH"
checklist_step "build efency" make -j
checklist_step "build efency BPF programs" make ebpf -j

checklist_done
