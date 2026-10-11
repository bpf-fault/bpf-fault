#!/bin/bash
# Builds the MMTk garbage collector with bpf_fault support: the OpenJDK
# fork with the MMTk third-party heap, the mmtk-openjdk binding against
# our mmtk-core, the bpf_fault handler shim, and the DaCapo benchmark
# suite the GC experiments run.
#
# Requires install_kernel.sh to have been run: the shim builds a static
# libbpf and bpftool out of the bpf-fault kernel tree, and generates its
# BPF skeletons from the running kernel's BTF.
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(dirname $SCRIPT_PATH)
GC_PATH="$BASE_DIR/gc-bpf-fault"
JDK_PATH="$BASE_DIR/openjdk"
DACAPO_PATH="$BASE_DIR/dacapo"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

# rustup installs into ~/.cargo/bin without touching the shell profile, so
# put it on PATH here: the OpenJDK build shells out to cargo to build the
# binding, and to cargo read-manifest for its version check.
export PATH="$HOME/.cargo/bin:$PATH"

DACAPO_URL="https://download.dacapobench.org/chopin/dacapo-23.11-MR2-chopin.zip"
DACAPO_SHA256="70a1fd4ed959f09053bb7ef8b2745a19d6f28dd8a7d0b350362039d89b49eb26"

# Prime sudo credentials before output is redirected to the log
sudo -v

install_deps() {
	sudo apt-get update
	# The OpenJDK build needs a bootstrap JDK and the X11/font/ALSA
	# headers; bpftrace measures GC pause windows in the run scripts;
	# clang-20 compiles the BPF arena handler; zip tools unpack DaCapo.
	sudo apt-get install -y build-essential autoconf zip unzip curl \
		openjdk-21-jdk libx11-dev libxext-dev libxrender-dev \
		libxrandr-dev libxtst-dev libxt-dev libcups2-dev \
		libfontconfig1-dev libasound2-dev bpftrace clang-20
	if ! command -v cargo > /dev/null; then
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
			| sh -s -- -y --no-modify-path
	fi
}

init_submodules() {
	git -C "$BASE_DIR" submodule update --init \
		mmtk-core mmtk-openjdk gc-bpf-fault openjdk
}

configure_jdk() {
	cd "$JDK_PATH"
	# --with-conf-name fixes the build directory, so the run scripts can
	# find the image without knowing the host triple.
	sh configure --disable-warnings-as-errors \
		--with-debug-level=release --with-conf-name=mmtk
}

build_jdk() {
	cd "$JDK_PATH"
	# THIRD_PARTY_HEAP builds the mmtk-openjdk binding (and, through its
	# path dependency, our mmtk-core) into the JVM. "images" is required:
	# the exploded image is not valid for performance measurement.
	#
	# MMTK_VO_BIT compiles in the valid-object bit, which GenImmix dirty
	# tracking needs to walk a dirty page's objects; without it the
	# dirty-tracking configurations panic at plan creation.
	MMTK_VO_BIT=1 make CONF=mmtk \
		THIRD_PARTY_HEAP="$BASE_DIR/mmtk-openjdk/openjdk" images
}

fetch_dacapo() {
	local zip="$DACAPO_PATH/dacapo-23.11-MR2-chopin.zip"
	mkdir -p "$DACAPO_PATH"
	curl -fL -o "$zip" "$DACAPO_URL"
	echo "$DACAPO_SHA256  $zip" | sha256sum -c -
	# The jar looks for its data in a directory of the same name beside
	# it, so extract the whole archive (~16 GB), not just the jar.
	unzip -o -q "$zip" -d "$DACAPO_PATH"
	rm -f "$zip"
	test -f "$DACAPO_PATH/dacapo-23.11-MR2-chopin.jar"
	test -d "$DACAPO_PATH/dacapo-23.11-MR2-chopin"
}

smoke_test() {
	# The handler is the piece most likely to break against a rebuilt
	# kernel: check it still verifies before spending hours in DaCapo.
	sudo "$GC_PATH/shim/loadcheck"
}

checklist_init "install_gc" 8 "$BASE_DIR/results/logs/install-gc.log"

checklist_step "install dependencies" install_deps

# All four must be present: the step initializes them together, and the
# OpenJDK build needs the binding and mmtk-core alongside the JDK tree.
if [[ -e "$GC_PATH/shim/Makefile" && -e "$JDK_PATH/configure" \
	&& -e "$BASE_DIR/mmtk-core/Cargo.toml" \
	&& -e "$BASE_DIR/mmtk-openjdk/mmtk/Cargo.toml" ]]; then
	checklist_skip "initialize gc submodules" "already checked out"
else
	checklist_step "initialize gc submodules" init_submodules
fi

checklist_step "build the bpf_fault shim" \
	make -C "$GC_PATH/shim" KDIR="$BASE_DIR/linux" -j"$(nproc)"

if [[ -e "$JDK_PATH/build/mmtk/spec.gmk" ]]; then
	checklist_skip "configure openjdk" "already configured"
else
	checklist_step "configure openjdk" configure_jdk
fi

checklist_step "build openjdk with mmtk (this takes a while)" build_jdk

# Both the jar and its data directory, for the same reason as the
# submodule guard above: a half-extracted archive must not be skipped.
if [[ -e "$DACAPO_PATH/dacapo-23.11-MR2-chopin.jar" \
	&& -d "$DACAPO_PATH/dacapo-23.11-MR2-chopin" ]]; then
	checklist_skip "download DaCapo 23.11-MR2" "already downloaded"
else
	checklist_step "download DaCapo 23.11-MR2" fetch_dacapo
fi

checklist_step "verify the MMTk JDK" \
	"$JDK_PATH/build/mmtk/images/jdk/bin/java" -XX:+UseThirdPartyHeap -version
checklist_step "verify the bpf_fault handler loads" smoke_test

checklist_done
