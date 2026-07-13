#!/bin/bash
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
MEMTIER_PATH="$BASE_DIR/memtier_benchmark"

. "$BASE_DIR/eval/lib.sh"

# Prime sudo credentials before output is redirected to the log
sudo -v

install_deps() {
	sudo apt-get update
	sudo apt-get install -y build-essential autoconf automake libpcre3-dev \
				libevent-dev pkg-config zlib1g-dev libssl-dev
}

configure_memtier() {
	autoreconf -ivf
	./configure
}

build_install_memtier() {
	make -j
	sudo make install
}

verify_memtier() {
	# The snapshot benchmark requires the fork's --stats-interval flag.
	# --help exits non-zero by design, so don't pipe it directly into
	# grep under pipefail.
	local help_output
	help_output=$(memtier_benchmark --help 2>&1 || true)
	if ! grep -q "stats-interval" <<<"$help_output"; then
		echo "Installed memtier_benchmark does not support --stats-interval."
		return 1
	fi
	echo "memtier_benchmark installed: $(command -v memtier_benchmark)"
}

checklist_init "install_memtier" 5 "$BASE_DIR/results/logs/install-memtier.log"

checklist_step "install dependencies" install_deps

if [[ -e "$MEMTIER_PATH/configure.ac" ]]; then
	checklist_skip "initialize memtier_benchmark submodule" "already checked out"
else
	checklist_step "initialize memtier_benchmark submodule" \
		git -C "$BASE_DIR" submodule update --init memtier_benchmark
fi

cd "$MEMTIER_PATH"
checklist_step "configure memtier_benchmark" configure_memtier
checklist_step "build and install memtier_benchmark" build_install_memtier
checklist_step "verify --stats-interval support" verify_memtier

checklist_done "memtier_benchmark installed to $(command -v memtier_benchmark 2>/dev/null || echo /usr/local/bin/memtier_benchmark)"
