# Firecracker Snapshot Benchmark (Figures 8 and 9)

Compares three VM snapshot modes in our Firecracker fork:

- `full` — synchronous (stop-the-world) snapshot
- `live` — live snapshot using userfaultfd write protection
- `live_bpf` — live snapshot using `bpf_fault`

For each mode and VM memory size, the benchmark runs a guest workload
(redis/memcached driven by our memtier_benchmark fork, or STREAM) and measures
downtime, total snapshot time, and throughput/latency timeseries during the
snapshot (100 ms samples).

Requires `install_memtier.sh` and `install_firecracker.sh` to have been run, KVM
access, and the system booted into the `bpf-fault` kernel. See
`firecracker/docs/snapshot-benchmark-runbook.md` for full details.

## Usage

```sh
./run.sh                                    # redis_heavy + memcached_heavy, 3 iterations, 4/8 GiB
./plot.sh                                   # Figure 8 panel candidates + figure9{a,b}.pdf
```

`plot.sh` generates a Figure 8 timeline plot for every iteration
(`figures/snapshot_timeseries_<workload>/figure8<panel>_..._iter<N>.pdf`),
controlled by `FIG8_WORKLOAD`/`FIG8_MEM` (default: redis_heavy at
8192 MiB); pick each panel's iteration by hand from those candidates.

The run reuses completed configurations: an interrupted sweep resumes
where it stopped. The raw data accumulates in
`firecracker/test_results/`; delete `experiment_results.csv` there (or
pass `--no-reuse-results` to `run_snapshot_benchmark.py` directly) to
force a full re-measurement.

This should take approximately 30 minutes.
