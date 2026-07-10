# Fault-Handling Overhead Breakdown

Instruments the page fault path with BPF kprobes to attribute per-fault time
to individual phases (syscall entry, wakeup, copy, etc.), producing a
two-lane (faulting thread / handler thread) timeline for the baseline
kernel zero-fill path, userfaultfd, and `bpf_fault`.

The benchmark binaries live in the kernel tree at
`linux/tools/testing/selftests/bpf/bench_fault/` and must run on the
`bpf-fault` kernel with root privileges.

## Usage

```sh
./run.sh    # saves results/overhead{,_baseline,_bpf}.csv
./plot.sh   # generates figures/overhead_*.pdf
```

Environment knobs for `run.sh`:

- `ITERATIONS` (default: 3) — rounds per configuration
- `PAGES` (default: 4096) — pages faulted per round

Expected runtime: a few minutes.
