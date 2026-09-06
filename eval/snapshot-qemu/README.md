# QEMU Snapshot Benchmark (Table 4)

Compares four VM snapshot modes in our QEMU fork:

- `full` — synchronous snapshot (pause, migrate RAM+state to file, resume)
- `migrate` — stock live migration to file (dirty-tracking baseline)
- `live` — background snapshot using userfaultfd write protection
- `live_bpf` — background snapshot using `bpf_fault`
  (`x-bpf-fault-snapshot=on`)

For each mode and VM memory size, the benchmark runs Redis in the guest under
our memtier_benchmark fork and measures downtime, total snapshot time, and
throughput/latency timeseries during the snapshot (100 ms samples), in the
same results schema as the Firecracker snapshot experiment.

The `migrate` baseline is iterative pre-copy: it re-sends every re-dirtied
page, so its stop-the-world downtime depends on how fast the guest dirties
memory, and under a sufficiently write-heavy workload it may never converge.
A run that has not converged after `MIGRATE_TIMEOUT` seconds (default 120) is
cancelled and recorded with `converged: false`. At the sizes reported here it
does converge; the background-snapshot modes copy each page exactly once and
so are bounded by construction.

Requires `install_memtier.sh`, `install_firecracker.sh` (guest artifacts), and
`install_qemu.sh` to have been run, KVM access, and the system booted into the
`bpf-fault` kernel.

## Usage

```sh
./run.sh    # redis_heavy, 4 modes, 3 iterations, 8/16 GiB
./plot.sh   # generates the Table 4 LaTeX table
```

`run.sh` accepts `WORKLOADS`, `ITERATIONS`, `MEM_SIZES`, `MODES`, and
`MIGRATE_TIMEOUT` environment variables.

Expected runtime: 25 minutes.
