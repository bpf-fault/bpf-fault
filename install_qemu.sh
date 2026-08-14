#!/bin/bash
# Builds QEMU with bpf_fault snapshot support and prepares the QEMU
# snapshot benchmark. Arguments are forwarded to setup_experiment.sh
# (e.g. --skip-deps, --skip-build, --no-smoke-test).
#
# Requires install_firecracker.sh to have run: the benchmark reuses its
# guest kernel, app rootfs, and ssh key.
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
QEMU_PATH="$BASE_DIR/qemu"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# Prime sudo credentials before output is redirected to the log
sudo -v

checklist_init "install_qemu" 7 "$BASE_DIR/results/logs/install-qemu.log"

if [[ -e "$QEMU_PATH/meson.build" ]]; then
	checklist_skip "initialize qemu submodule" "already checked out"
else
	checklist_step "initialize qemu submodule" \
		git -C "$BASE_DIR" submodule update --init qemu
fi

# setup_experiment.sh announces each phase; map announcements onto the
# remaining checklist steps.
cd "$QEMU_PATH"
./tests/bpf-fault-bench/setup_experiment.sh "$@" 2>&1 | checklist_filter \
	-M '^error:' 's/^error: */error: /' \
	'^(Installing build dependencies|Skipping build dependencies|Generating BPF skeleton|Skipping BPF skeleton|Building QEMU|Skipping QEMU build|Verifying bpf_fault support|Checking guest artifacts|Running synthetic smoke|Skipping smoke test)' \
	's/^(Installing|Skipping) build dependencies.*/install build dependencies/;
	 s/^(Generating|Skipping) BPF skeleton.*/generate BPF skeleton/;
	 s/^(Building QEMU|Skipping QEMU build).*/build qemu-system-x86_64/;
	 s/^Verifying bpf_fault support.*/verify the built binary/;
	 s/^Checking guest artifacts.*/check guest artifacts (from install_firecracker.sh)/;
	 s/^(Running synthetic smoke|Skipping smoke) test.*/run synthetic smoke test/'

checklist_done
