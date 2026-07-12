#!/bin/bash
set -eu -o pipefail

# Tools required for running benchmarks and plotting figures

echo "Installing additional tools..."
sudo apt-get update
# Tools:
#   python3-numpy: Required for Python plotting scripts
#   python3-pandas: Required for Python plotting scripts
#   python3-matplotlib: Required for Python plotting scripts
#   python3-psutil: Required by the scalability benchmark for CPU sampling
#   screen: Required for running long-running scripts in the background
sudo apt-get install -y python3-numpy python3-pandas \
			python3-matplotlib python3-psutil screen
