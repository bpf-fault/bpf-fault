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
Docker); the FFmpeg source is cloned by the configure benchmark itself.

## Usage

```sh
./run.sh    # runs all benchmarks; saves results/dynlink/
./plot.sh   # generates figures/figure10{a,b,c}.pdf
```

Expected runtime: a few hours (50 runs per configuration).
