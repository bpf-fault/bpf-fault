# efency Benchmarks (Figure 11)

Compares allocator modes — glibc, the original efence, efency (SIGBUS and
handler-thread variants), and ebpfency (the `bpf_fault`-based variant) —
on:

- a malloc throughput microbenchmark
- a fork benchmark
- application benchmarks

Requires `install_efency.sh` to have been run, and the system booted into
the `bpf-fault` kernel (for the ebpfency mode).

## Usage

```sh
./run.sh                # 3 iterations, all modes; saves results/efency/*.json
ITERATIONS=5 ./run.sh   # more iterations
./run.sh --skip-apps    # extra args are forwarded to efency's run_all.sh
./plot.sh               # generates figures/figure11{a,b}.pdf
```

Expected runtime: the application benchmarks are slow under efence; budget
several hours for a full run (use `--skip-apps` for a quick pass).
