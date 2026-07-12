#!/bin/bash
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
MEMTIER_PATH="$BASE_DIR/memtier_benchmark"

echo "Installing memtier_benchmark dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential autoconf automake libpcre3-dev \
			libevent-dev pkg-config zlib1g-dev libssl-dev

cd "$MEMTIER_PATH"
if [[ ! -e "configure.ac" ]]; then
	git submodule update --init
fi

echo "Building memtier_benchmark..."
autoreconf -ivf
./configure
make -j
sudo make install

# The snapshot benchmark requires the fork's --stats-interval flag.
# --help exits non-zero by design, so don't pipe it directly into grep under pipefail.
help_output=$(memtier_benchmark --help 2>&1 || true)
if ! grep -q "stats-interval" <<<"$help_output"; then
	echo "Installed memtier_benchmark does not support --stats-interval."
	exit 1
fi

echo "memtier_benchmark installed: $(command -v memtier_benchmark)"
