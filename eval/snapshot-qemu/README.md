# QEMU Snapshot Benchmark (QEMU Figure 9 variants)

Compares four VM snapshot modes in our QEMU fork:

- `full` — synchronous snapshot (pause, migrate RAM+state to file, resume)
- `migrate` — stock live migration to file (dirty-tracking baseline)
- `live` — background snapshot using userfaultfd write protection
- `live_bpf` — background snapshot using `bpf_fault`
  (`x-bpf-fault-snapshot=on`)

For each mode and VM memory size, the benchmark runs a guest workload
(redis/memcached driven by our memtier_benchmark fork) and measures downtime,
total snapshot time, and throughput/latency timeseries during the snapshot
(100 ms samples), in the same results schema as the Firecracker snapshot
experiment.

The `migrate` baseline demonstrates non-convergence: iterative pre-copy
re-sends every re-dirtied page, so under the write-heavy workloads the
migration cannot finish. It is cancelled after a 120 s timeout and recorded
with `converged: false`; the background-snapshot modes copy each page exactly
once and complete in bounded time.

Requires `install_memtier.sh`, `install_firecracker.sh` (guest artifacts), and
`install_qemu.sh` to have been run, KVM access, and the system booted into the
`bpf-fault` kernel.

## Usage

```sh
./run.sh    # redis_heavy + memcached_heavy, 4 modes, 3 iterations, 4/8 GiB
./plot.sh   # figure9{a,b}_qemu.pdf (FC + QEMU side by side) + timelines
```

Expected runtime: 45 minutes (the `migrate` mode spends its full 120 s
timeout in every write-heavy configuration).
