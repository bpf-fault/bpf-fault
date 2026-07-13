# efency Benchmarks (Figure 11)

Compares allocator modes — glibc, the original Electric Fence, efency
(SIGBUS and handler-thread variants), and ebpfency (the `bpf_fault`-based
variant) — on:

- malloc microbenchmarks (Figure 11a): all five modes, normalized to
  glibc
- application benchmarks (Figure 11b): clang, ripgrep, git status,
  python, and jq, without Electric Fence, which crashes on most of these
  applications

Requires `install_efency.sh` to have been run, and the system booted into
the `bpf-fault` kernel (for the ebpfency mode).

## Usage

```sh
./run.sh                # 3 iterations; saves results/efency/*.json
./plot.sh               # generates figures/figure11{a,b}.pdf
```

This is expected to take approximately 15 minutes.
