#!/bin/bash
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
LINUX_PATH="$BASE_DIR/linux"

. "$BASE_DIR/eval/lib.sh"

# Prime sudo credentials before output is redirected to the log
sudo -v

install_deps() {
	sudo apt-get update
	sudo apt-get install -y build-essential bc bison flex rsync libelf-dev \
				libssl-dev libncurses-dev dwarves clang lld \
				llvm python3
}

configure_kernel() {
	make olddefconfig
	# Ignore 'yes' exit status
	{ yes '' || true; } | make localmodconfig
	scripts/config --set-str LOCALVERSION "-bpf-fault"
	scripts/config --set-str SYSTEM_TRUSTED_KEYS ''
	scripts/config --set-str SYSTEM_REVOCATION_KEYS ''
}

build_install_kernel() {
	# build.py prompts for confirmation; answer with enter
	{ yes '' || true; } | python3 build.py install
}

install_libbpf() {
	# Default location:
	#	Library: /usr/local/lib64/libbpf.{a,so}
	#	Headers: /usr/local/include/bpf
	sudo make -C tools/lib/bpf -j install
	if [[ ! -e /etc/ld.so.conf.d/libbpf.conf ]]; then
		echo "/usr/local/lib64" | sudo tee /etc/ld.so.conf.d/libbpf.conf > /dev/null
		sudo ldconfig
		echo "Added /usr/local/lib64 to /etc/ld.so.conf.d/libbpf.conf"
	else
		echo "/usr/local/lib64 already exists in /etc/ld.so.conf.d/libbpf.conf"
	fi
}

install_bpftool() {
	# Default location:
	#	Binary: /usr/local/sbin/bpftool (version v7.7.0)
	sudo make -C tools/bpf/bpftool -j install
}

setup_boot() {
	if [[ -z "$(sudo awk -F\' '/menuentry / {print $2}' /boot/grub/grub.cfg | grep -m 1 'Ubuntu, with Linux 6.17.0-bpf-fault+')" ]]; then
		echo "Cannot find bpf_fault kernel. Please install the kernel manually."
		return 1
	fi
	if ! sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-bpf-fault+"; then
		echo "grub-reboot with bpf_fault kernel failed. Please boot into the kernel manually."
		return 1
	fi
}

checklist_init "install_kernel" 8 "$BASE_DIR/results/logs/install-kernel.log"

checklist_step "install build dependencies" install_deps

if [[ -e "$LINUX_PATH/Makefile" ]]; then
	checklist_skip "initialize linux submodule" "already checked out"
else
	checklist_step "initialize linux submodule" \
		git -C "$BASE_DIR" submodule update --init --recursive linux
fi

cd "$LINUX_PATH"
checklist_step "clean previous build" sudo make distclean
checklist_step "configure kernel (localmodconfig, bpf-fault)" configure_kernel
checklist_step "build and install kernel" build_install_kernel
checklist_step "build and install libbpf" install_libbpf
checklist_step "build and install bpftool" install_bpftool
checklist_step "verify grub entry, set one-shot boot" setup_boot

checklist_done "To boot into the bpf_fault kernel, run: sudo reboot now"
