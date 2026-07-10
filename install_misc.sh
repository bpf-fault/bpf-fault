#!/bin/bash
set -eu -o pipefail

# Tools required for running benchmarks and plotting figures

echo "Installing additional tools..."
sudo apt-get update
# Tools:
#   build-essential: Required for building benchmark components
#   clang: Required for building BPF programs
#   python3-numpy: Required for Python plotting scripts
#   python3-pandas: Required for Python plotting scripts
#   python3-matplotlib: Required for Python plotting scripts
#   screen: Required for running long-running scripts in the background
sudo apt-get install -y build-essential clang make git curl \
			python3 python3-numpy python3-pandas \
			python3-matplotlib screen
