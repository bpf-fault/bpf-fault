# Dynamic Linking Benchmarks (Figure 10)

Evaluates deferred ELF relative relocations via BPF page-fault handling
(`bpf-dynlink`): a patched glibc dynamic linker defers `R_X86_64_RELATIVE`
relocations, and a BPF program applies them on demand at fault time.

Benchmarks:

- Synthetic microbenchmarks (4K / 100K / 1M relocations, no-touch)
- `dlopen` with 1M relocations
- Real-application startup and steady-state workloads (Clang, Deno,
  Chrome, Node, Docker, ffmpeg `configure`)

Requires `install_dynlink.sh` to have been run, and the system booted into
the `bpf-fault` kernel. The benchmark scripts load the BPF relocation
handler and set `fault_around_bytes` themselves. `install_dynlink.sh`
installs the application workloads (clang, ld.lld, Deno, Chrome, Node,
Docker).

## Usage

```sh
./run.sh    # runs all benchmarks; saves results/dynlink/
./plot.sh   # generates figures/figure10{a,b,c}.pdf
```

Iteration counts are set per benchmark in the bpf-dynlink repo's
`test_e2e/run_all_benchmarks.sh` (50 for the microbenchmarks and Clang,
fewer for the slower application workloads).

Expected runtime: a few minutes.
