#!/bin/bash
# Builds Firecracker, downloads the guest kernel and rootfs images, and
# builds the app rootfs. Arguments are forwarded to setup_experiment.sh
# (e.g. --skip-build, --skip-rootfs, --no-smoke-test).
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
FC_PATH="$BASE_DIR/firecracker"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# Prime sudo credentials before output is redirected to the log
sudo -v

checklist_init "install_firecracker" 10 "$BASE_DIR/results/logs/install-firecracker.log"

if [[ -e "$FC_PATH/Cargo.toml" ]]; then
	checklist_skip "initialize firecracker submodule" "already checked out"
else
	checklist_step "initialize firecracker submodule" \
		git -C "$BASE_DIR" submodule update --init firecracker
fi

# setup_experiment.sh expects the fork's memtier_benchmark on PATH; run
# ./install_memtier.sh first. Its phase announcements drive the
# remaining checklist steps.
cd "$FC_PATH"
./setup_experiment.sh "$@" 2>&1 | checklist_filter \
	-M '^(Adding .* docker group|Re-executing|Removing incomplete artifact|Expanding image|Mounting image|Installing packages inside chroot|Verifying rootfs)' \
	's/^Adding.*/adding user to the docker group/; s/^Re-executing.*/re-executing under the docker group/; s/^Removing incomplete.*/removing incomplete artifacts/; s/^Expanding image.*/expanding image/; s/^Mounting image.*/mounting image/; s/^Installing packages inside chroot.*/installing packages in chroot/; s/^Verifying rootfs.*/verifying/' \
	'^(Installing AWS CLI|Skipping AWS CLI|Installing docker\.io|Skipping docker\.io|Granting .* /dev/kvm|Skipping /dev/kvm|Compiling BPF fault-ops|Skipping BPF fault-ops|Building Firecracker|Skipping Firecracker build|Downloading and converting|Skipping artifact download|Checking memtier_benchmark|Skipping memtier_benchmark|Copying base rootfs|Skipping app rootfs|Running quick synthetic smoke|Skipping smoke test)' \
	's/^(Installing|Skipping) AWS CLI.*/install AWS CLI/;
	 s/^(Installing|Skipping) docker\.io.*/install docker.io/;
	 s@^(Granting|Skipping).*kvm.*@grant /dev/kvm access@;
	 s/^(Compiling|Skipping) BPF fault-ops.*/compile BPF fault-ops object/;
	 s/^(Building Firecracker|Skipping Firecracker build).*/build Firecracker (release)/;
	 s/^(Downloading and converting|Skipping artifact download).*/download and convert test artifacts/;
	 s/^(Checking|Skipping) memtier_benchmark.*/check memtier_benchmark for --stats-interval/;
	 s/^(Copying base rootfs|Skipping app rootfs).*/build app rootfs/;
	 s/^(Running quick synthetic smoke|Skipping smoke test).*/run synthetic smoke test/'

checklist_done "Log out and log back in for user group changes to take effect."
