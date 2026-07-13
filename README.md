# bpf_fault: Customizable Page Fault Handling with eBPF

This repository contains source code and scripts for reproducing key results
from the bpf_fault paper (SOSP 2026) for the purposes of artifact evaluation.

We use a CloudLab instance of type c6525-25g running Ubuntu 24.04, with a
maxed out temporary disk (`/mydata`). KVM access is required for the
Firecracker experiments.

There are five major components, included as submodules:

- A modified Linux kernel based on Linux v6.17 that supports `bpf_fault`. This
  also includes supporting changes to libbpf and bpftool, and fault-handling
  microbenchmarks.
- efency: an efficient electric-fence malloc() debugger, including ebpfency, a
  `bpf_fault`-based variant.
- bpf-dynlink: deferred ELF relative relocations via BPF page-fault handling,
  including a patched glibc 2.41 dynamic linker.
- Firecracker with live snapshot support via userfaultfd and `bpf_fault`.
- memtier_benchmark with a `--stats-interval` flag for fine-grained
  throughput/latency timeseries during snapshots.

## Repository Structure

```
bpf-fault
|-- bench/                  : Plotting scripts and shared benchmark libraries
|-- eval/                   : Evaluation scripts, one directory per experiment
|   |-- fault-latency/      : Page fault latency microbenchmark
|   |-- scalability/        : Fault-handling scalability experiment
|   |-- efency/             : efency allocator benchmarks
|   |-- dynlink/            : Dynamic linking benchmarks
|   \-- snapshot/           : Firecracker snapshot experiment
\-- install_*.sh            : Component installation and build scripts
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

This will also set up libbpf and bpftool, and configure grub to boot the
bpf-fault kernel on the next reboot. When it completes, reboot into it:

```sh
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
kernel and Ubuntu rootfs images from S3 and builds the application rootfs on top
of them. Note that `install_memtier.sh` must run before
`install_firecracker.sh`, which depends on the installed `memtier_benchmark`.

## Running Experiments

The experiment scripts are located in the `eval` directory. Each subdirectory
contains a `run.sh` script that sets up the environment and runs the experiment,
and a `README.md` describing it.

To run every experiment and generate every figure in one invocation:

```sh
cd /mydata/bpf-fault/eval
./run_all.sh
```

A failure in one experiment does not stop the others; a summary is printed at
the end.

By default, experiments run 3 iterations to get an average result; most run
scripts accept an `ITERATIONS` environment variable to change this.

Results are saved in the top-level `results/` directory.

Running the experiments takes about an hour (see each experiment's README for
estimates). We recommend using `screen` to run them in a persistent session that
survives SSH disconnects. To detach from a `screen` session, press
<kbd>Ctrl</kbd> + <kbd>A</kbd> followed by <kbd>Ctrl</kbd> + <kbd>D</kbd>.

All run and plot scripts show a compact live progress display with the current
step and its log file; the underlying tool output is written to `results/logs/`.
Set `VERBOSE=1` to stream the raw output instead. Run scripts reuse results from
completed configurations, so an interrupted experiment resumes where it stopped,
and only one instance of each script can run at a time.

## Plotting Results

Each experiment directory contains a `plot.sh` script that generates its figures
from `results/` into the top-level `figures/` directory, named after the
corresponding paper figure (e.g., `figure10a.pdf`):

```sh
cd /mydata/bpf-fault/eval/fault-latency
./plot.sh
```

The underlying plotting scripts live in `bench/` and can also be invoked
directly. The `run_all.sh` script runs the plotting scripts as well.

## Citation

If using bpf_fault, please include the following citation:

```bibtex
TODO
```
