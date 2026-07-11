#!/bin/bash
set -eu -o pipefail

# Install Linux build dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential bc bison flex rsync libelf-dev \
			libssl-dev libncurses-dev dwarves clang lld \
			llvm python3

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
LINUX_PATH="$BASE_DIR/linux"

cd "$LINUX_PATH"
if [[ ! -e "Makefile" ]]; then
    git submodule update --init --recursive
fi

# Clean previous builds
sudo make distclean

echo "Configuring kernel..."
make olddefconfig

# Ignore 'yes' exit status
{ yes '' || true;} | make localmodconfig

scripts/config --set-str LOCALVERSION "-bpf-fault"
scripts/config --set-str SYSTEM_TRUSTED_KEYS ''
scripts/config --set-str SYSTEM_REVOCATION_KEYS ''

# localmodconfig strips these since they aren't in use by the currently
# running kernel, but Docker's default bridge network needs them.
echo "Enabling netfilter/bridge modules required for Docker networking..."
# NETFILTER_XTABLES gates the "-m addrtype"/"-m conntrack"/MASQUERADE match
# extensions below (net/netfilter/Kconfig); without it enabled first,
# olddefconfig silently drops those as unreachable.
scripts/config --module CONFIG_NETFILTER_XTABLES
scripts/config --module CONFIG_BRIDGE
scripts/config --module CONFIG_BRIDGE_NETFILTER
scripts/config --module CONFIG_VETH
scripts/config --module CONFIG_NF_CONNTRACK
scripts/config --module CONFIG_NF_NAT
scripts/config --module CONFIG_IP_NF_NAT
scripts/config --module CONFIG_IP_NF_FILTER
scripts/config --module CONFIG_IP_NF_TARGET_MASQUERADE
scripts/config --module CONFIG_NETFILTER_XT_MATCH_ADDRTYPE
scripts/config --module CONFIG_NETFILTER_XT_MATCH_CONNTRACK
scripts/config --module CONFIG_NETFILTER_XT_TARGET_MASQUERADE
scripts/config --module CONFIG_NFT_CHAIN_NAT
scripts/config --module CONFIG_NFT_NAT
scripts/config --module CONFIG_NFT_MASQ
scripts/config --module CONFIG_NFT_CT
scripts/config --module CONFIG_NFT_COMPAT
# containerd's default snapshotter needs overlayfs.
scripts/config --module CONFIG_OVERLAY_FS
make olddefconfig

echo "Building and installing the kernel..."
echo "If prompted, hit enter to continue."
python3 build.py install

echo "Building and installing libbpf..."
# Default location:
#	Library: /usr/local/lib64/libbpf.{a,so}
#	Headers: /usr/local/include/bpf
sudo make -C tools/lib/bpf -j install

# Add ld.so.conf.d entry for libbpf
if [[ ! -e /etc/ld.so.conf.d/libbpf.conf ]]; then
	echo "/usr/local/lib64" | sudo tee /etc/ld.so.conf.d/libbpf.conf > /dev/null
	sudo ldconfig
	echo "Added /usr/local/lib64 to /etc/ld.so.conf.d/libbpf.conf"
else
	echo "/usr/local/lib64 already exists in /etc/ld.so.conf.d/libbpf.conf"
fi

echo "Building and install bpftool..."
# Default location:
#	Binary: /usr/local/sbin/bpftool (version v7.7.0)
sudo make -C tools/bpf/bpftool -j install

if [[ -z "$(sudo awk -F\' '/menuentry / {print $2}' /boot/grub/grub.cfg | grep -m 1 'Ubuntu, with Linux 6.17.0-bpf-fault+')" ]]; then
	echo "Cannot find bpf_fault kernel. Please install the kernel manually."
	exit 1
fi

if ! sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-bpf-fault+"; then
	echo "grub-reboot with bpf_fault kernel failed. Please boot into the kernel manually."
	# echo -e "    sudo grub-reboot \"Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-bpf-fault+\""
	exit 1
fi

echo "bpf_fault kernel installed successfully. To boot into it, please run:"
echo -e "    sudo reboot now"
