# Fault-Handling Scalability (Figures 3b and 7)

Measures fault-handling throughput/latency as the number of concurrent
faulting threads scales, comparing the baseline kernel path, userfaultfd,
and SIGSEGV-based handling.

The benchmark lives in the kernel tree at
`linux/tools/testing/selftests/bpf/bench_fault/` and must run on the
`bpf-fault` kernel with root privileges.

## Usage

```sh
./run.sh    # runs the benchmark, saves results/scale_results.json
./plot.sh   # generates figures/figure3b.pdf and figures/figure7.pdf
```

Iterations, page counts, and modes are controlled by
`run_scale_motivation.sh` in the kernel tree (defaults: 3 iterations,
64 pages, `baseline,uffd,sigsegv`).

Note: `bench/plot_scale_cdf.py` both runs and plots a per-fault latency CDF
variant of this experiment; invoke it directly from `bench/` if needed.
