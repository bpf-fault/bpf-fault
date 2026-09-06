# Garbage Collection Benchmarks (Table 5)

Evaluates `bpf_fault` in two MMTk garbage collection mechanisms, both replacing
a `userfaultfd` integration with in-kernel fault handling. The benchmarks are
DaCapo 23.11-MR2 (chopin) on OpenJDK 21 with the MMTk third-party heap.

- Concurrent compaction (Table 5): the Compressor compacts the heap while
  mutators run, materializing each page on demand when a mutator touches it.
  Compares `None` (stop-the-world), `Uffd` (`UFFDIO_COPY` from a SIGBUS
  handler), and `R1` (the page built in-kernel), at 1.5x each benchmark's
  minimum heap.
- Dirty tracking: GenImmix's compiled write barrier is replaced by a
  page-protection remembered set. Compares `Barrier`, `Segv`, `Uffd`, and
  `Bpf` at a 4 GB heap. The paper quotes these in the text of Section 6.4
  rather than as a numbered table.

Requires `install_gc.sh` to have been run, and the system booted into the
`bpf-fault` kernel.

## Usage

```sh
./run.sh    # 3 invocations per configuration; saves results/gc/*.json
./plot.sh   # generates gc_table.tex and gc_dirty_table.tex
```

`run.sh` accepts `ITERATIONS` (invocations per configuration, default 3),
`DACAPO_ITERS` (DaCapo iterations per invocation, default 6; the last is the
steady-state measurement), and `COMPACTION`/`TRACKING` to narrow the benchmark
set. Pause times come from a second, bpftrace-instrumented invocation of each
compaction configuration.

Expected runtime: 4 hours, of which h2 alone is about 2.5 hours.
