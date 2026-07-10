# bpf_fault: Customizable Page Fault Handling with eBPF

This repository contains source code and scripts for reproducing key results
from the bpf_fault paper for the purposes of artifact evaluation.

We use a CloudLab instance of type c6525-25g running Ubuntu 24.04, with a
maxed out temporary disk (`/mydata`). KVM access is required for the
Firecracker experiments.

There are five major components, included as submodules:

- A modified Linux kernel based on Linux v6.17 that supports `bpf_fault`
  (programmable page fault handling via BPF struct_ops). This also includes
  supporting changes to libbpf and bpftool, and the fault-handling
  microbenchmarks (`tools/testing/selftests/bpf/bench_fault/`).
- efency: an efficient electric-fence malloc() debugger, including
  ebpfency, the `bpf_fault`-based variant.
- bpf-dynlink: deferred ELF relative relocations via BPF page-fault
  handling, including a patched glibc 2.41 dynamic linker.
- Firecracker with live snapshot support via userfaultfd and `bpf_fault`.
- memtier_benchmark with a `--stats-interval` flag for fine-grained
  throughput/latency timeseries during snapshots.

## Repository Structure

```text
bpf-fault
|-- linux/                  : Linux kernel with bpf_fault support + microbenchmarks
|-- efency/                 : efency/ebpfency malloc debugger
|-- bpf-dynlink/            : BPF deferred relocations (glibc + fault handler)
|-- firecracker/            : Firecracker with live snapshot support
|-- memtier_benchmark/      : memtier_benchmark fork (timeseries stats)
|-- bench/                  : Plotting scripts and shared benchmark libraries
|-- eval/                   : Evaluation scripts, one directory per experiment
|   |-- fault-latency/      : Page fault latency microbenchmark
|   |-- scalability/        : Fault-handling scalability experiment
|   |-- overhead/           : Fault-handling overhead breakdown
|   |-- efency/             : efency allocator benchmarks
|   |-- dynlink/            : Dynamic linking benchmarks
|   \-- snapshot/           : Firecracker snapshot experiment
|-- results/                : Experiment results (created by run scripts)
|-- figures/                : Generated figures (created by plot scripts)
\-- *.sh                    : Component installation and build scripts
```

## Getting Started

First, clone the repo into CloudLab's temporary disk (i.e., `/mydata`) and
initialize the submodules:

```sh
cd /mydata
git clone https://github.com/bpf-fault/bpf-fault.git
cd bpf-fault
git submodule update --init --recursive
```

Next, compile and install the custom Linux kernel:

```sh
./install_kernel.sh
```

This will also set up libbpf and bpftool.

After the kernel is compiled and installed, reboot into the bpf-fault
kernel:

```sh
sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-bpf-fault+"
sudo reboot now
```

The remaining components can only be compiled on the bpf-fault kernel (they
generate BPF type information from the running kernel), so wait for the
system to reboot and log back in.

Then, build and install the other components:

```sh
cd /mydata/bpf-fault
./install_misc.sh
./install_efency.sh
./install_dynlink.sh
./install_memtier.sh
./install_firecracker.sh
```

`install_firecracker.sh` downloads the Amazon-provided Firecracker CI guest
kernel and Ubuntu rootfs images from S3 and builds the application rootfs
on top of them; no separate dataset download is required.

## Running Experiments

Run the experiments in the `eval` directory. Each subdirectory contains a
`run.sh` script that sets up the environment and runs the experiment, and a
`README.md` describing it:

```sh
cd /mydata/bpf-fault/eval/fault-latency
./run.sh
```

By default, experiments run 3 iterations to get an average result; most run
scripts accept an `ITERATIONS` environment variable to change this.

Results are saved in the top-level `results/` directory.

Several experiments take multiple hours (see each experiment's README for
estimates). We recommend using `screen` to run them in a persistent session
that survives SSH disconnects. To detach from a `screen` session, press
<kbd>Ctrl</kbd> + <kbd>A</kbd> followed by <kbd>Ctrl</kbd> + <kbd>D</kbd>.

## Plotting Results

Each experiment directory contains a `plot.sh` script that generates its
figures from `results/` into the top-level `figures/` directory, named
after the corresponding paper figure (e.g., `figure10a.pdf`):

```sh
cd /mydata/bpf-fault/eval/fault-latency
./plot.sh
```

The underlying plotting scripts live in `bench/` and can also be invoked
directly (see `bench/benchplot.py --help` for the unified CLI).

## Citation

If using bpf_fault, please include the following citation:

```bibtex
TODO
```
