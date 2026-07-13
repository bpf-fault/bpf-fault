#!/bin/bash
# Tools required for running benchmarks and plotting figures
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)

. "$BASE_DIR/eval/lib.sh"

# Prime sudo credentials before output is redirected to the log
sudo -v

install_tools() {
	sudo apt-get update
	# Tools:
	#   python3-numpy: Required for Python plotting scripts
	#   python3-pandas: Required for Python plotting scripts
	#   python3-matplotlib: Required for Python plotting scripts
	#   python3-psutil: Required by the scalability benchmark for CPU sampling
	#   screen: Required for running long-running scripts in the background
	sudo apt-get install -y python3-numpy python3-pandas \
				python3-matplotlib python3-psutil screen
}

checklist_init "install_misc" 1 "$BASE_DIR/results/logs/install-misc.log"
checklist_step "install plotting and benchmark tools" install_tools
checklist_done
