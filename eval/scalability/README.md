# Fault-Handling Scalability (Figures 3b and 7)

Measures fault-handling throughput/latency as the number of concurrent
faulting threads scales, comparing the baseline kernel path, userfaultfd
(single- and multi-handler), SIGSEGV-based handling, and `bpf_fault`.

The benchmark lives in the kernel tree at
`linux/tools/testing/selftests/bpf/bench_fault/` and must run on the
`bpf-fault` kernel with root privileges.

## Usage

```sh
./run.sh    # runs the benchmark, saves results/scale_results.json
./plot.sh   # generates figures/figure3b.pdf and figures/figure7.pdf
```

`run.sh` accepts `ITERATIONS`, `PAGES`, and `MODES` environment variables
(defaults: 3 iterations, 64 pages per thread,
`baseline,uffd,uffd_mt,sigsegv,bpf`).

Expected runtime: 5 minutes.
