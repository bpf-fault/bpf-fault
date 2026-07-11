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
make -j"$(nproc)"
sudo cp memtier_benchmark /usr/local/bin/

# The snapshot benchmark requires the fork's --stats-interval flag.
# memtier_benchmark's --help path returns a non-zero exit status by design
# (memtier_benchmark.cpp: `case o_help: return -1;`), so under `set -o
# pipefail` a naive `memtier_benchmark --help | grep -q ...` always reports
# failure regardless of what grep actually matched. Capture the output
# separately so memtier_benchmark's exit code can't poison the pipeline.
help_output=$(memtier_benchmark --help 2>&1 || true)
if ! grep -q "stats-interval" <<<"$help_output"; then
	echo "Installed memtier_benchmark does not support --stats-interval."
	exit 1
fi

echo "memtier_benchmark installed: $(command -v memtier_benchmark)"
