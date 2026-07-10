# Page Fault Latency Microbenchmark (Figure 3a and Table 3)

Measures per-fault handling latency for userfaultfd vs `bpf_fault` across
fault types (anonymous, shmem, file-backed, write-protect).

The benchmark lives in the kernel tree at
`linux/tools/testing/selftests/bpf/bench_fault/` and must run on the
`bpf-fault` kernel with root privileges.

## Usage

```sh
./run.sh    # runs the benchmark, saves results/fault_results.json
./plot.sh   # generates figures/figure3a.pdf and the Table 3 LaTeX table
```

Iterations are controlled by `run_fault_bench.sh` in the kernel tree
(default: 3 rounds).

Expected runtime: a few minutes.
