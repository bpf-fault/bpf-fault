# Firecracker Snapshot Benchmark (Figures 6, 8, and 9)

Compares three VM snapshot modes in our Firecracker fork:

- `full` — synchronous (stop-the-world) snapshot
- `live` — live snapshot using userfaultfd write protection
- `live_bpf` — live snapshot using `bpf_fault`

For each mode and VM memory size, the benchmark runs a guest workload
(redis/memcached driven by our memtier_benchmark fork, or STREAM) and
measures downtime, total snapshot time, and throughput/latency timeseries
during the snapshot (100 ms samples).

Requires `install_memtier.sh` and `install_firecracker.sh` to have been
run, KVM access, and the system booted into the `bpf-fault` kernel.
See `firecracker/docs/snapshot-benchmark-runbook.md` for full details.

## Usage

```sh
./run.sh                                    # redis_heavy + memcached_heavy, 3 iterations, 4/8 GiB
WORKLOADS="redis_light redis_heavy" ./run.sh
ITERATIONS=1 MEM_SIZES=4096 ./run.sh        # quick smoke run (~15 min)
./plot.sh                                   # figures/figure6{a,b}.pdf, figure8{a,b,c}.pdf,
                                            # figure9{a,b}.pdf + per-workload detail plots
```

`plot.sh` takes Figure 8's panels from the `FIG8_WORKLOAD`/`FIG8_MEM`
configuration (default: redis_heavy at 8192 MiB).

Expected runtime: **approximately 2 hours per workload** for a full
3-iteration run. Use `screen` for long runs.

Note: the QEMU comparison for graph 4
(`results/qemu_snapshot_benchmark_redis.json`) is produced by a separate
QEMU harness and is not run by this script.
