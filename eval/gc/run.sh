#!/bin/bash
# Garbage collection run script (Table 5 and the dirty-tracking results
# in Section 6.4)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
GC_PATH="$BASE_DIR/gc-bpf-fault"
RESULTS_PATH="$BASE_DIR/results/gc"

. "$BASE_DIR/eval/lib.sh"

if ! uname -r | grep -q "bpf-fault"; then
	die "This script is intended to be run on a bpf_fault kernel."$'\n'"Please switch to the bpf_fault kernel and try again."
fi

export GC_JDK="${GC_JDK:-$BASE_DIR/openjdk/build/mmtk/images/jdk}"
export GC_DACAPO="${GC_DACAPO:-$BASE_DIR/dacapo/dacapo-23.11-MR2-chopin.jar}"
export MMTK_BPF_SHIM="${MMTK_BPF_SHIM:-$GC_PATH/shim/libgcbpf.so}"

if [[ ! -x "$GC_JDK/bin/java" ]]; then
	die "No MMTk JDK at $GC_JDK. Run ./install_gc.sh first."
fi

# Invocations per configuration, averaged in the table
ITERATIONS="${ITERATIONS:-3}"
# DaCapo iterations per invocation; the last is the steady-state
# measurement, the rest warm the JIT up
DACAPO_ITERS="${DACAPO_ITERS:-6}"

# Concurrent compaction (Table 5): Compressor at 1.5x each benchmark's
# minimum heap, stop-the-world vs the uffd and bpf_fault integrations.
COMPACTION="${COMPACTION:-h2:768M pmd:336M xalan:80M lusearch:128M}"
COMPACTION_CONFIGS="${COMPACTION_CONFIGS:-None,Uffd,R1}"

# Dirty tracking (Section 6.4): GenImmix at a 4 GB heap, the compiled
# write barrier vs the three page-protection backends.
TRACKING="${TRACKING:-h2 pmd xalan lusearch}"
TRACKING_HEAP="${TRACKING_HEAP:-4G}"
TRACKING_CONFIGS="${TRACKING_CONFIGS:-Barrier,Segv,Uffd,Bpf}"

mkdir -p "$RESULTS_PATH"

# Prime sudo credentials before output is redirected to the log
sudo -v

# One step per (config, invocation, record kind). Compaction runs a
# second, bpftrace-instrumented invocation per config to measure pause
# times; dirty tracking only needs throughput.
set -- $COMPACTION;  NB=$#
set -- $TRACKING;    NT=$#
NBC=$(($(tr -cd ',' <<< "$COMPACTION_CONFIGS" | wc -c) + 1))
NTC=$(($(tr -cd ',' <<< "$TRACKING_CONFIGS" | wc -c) + 1))
TOTAL=$(((NB * NBC * 2 + NT * NTC) * ITERATIONS))
progress_init "gc" "$TOTAL" "$BASE_DIR/results/logs/run-gc.log"

# The paper's stated machine configuration. Restored on exit, including
# on failure or Ctrl-C, so an interrupted run does not leave the machine
# with SMT and swap disabled.
SMT_CONTROL=/sys/devices/system/cpu/smt/control
gc_exit() {
	if [ -e "$SMT_CONTROL" ]; then
		echo on | sudo tee "$SMT_CONTROL" > /dev/null
	fi
	sudo swapon -a 2> /dev/null || true
	echo 2 | sudo tee /proc/sys/kernel/randomize_va_space > /dev/null
	_progress_exit
}
trap gc_exit EXIT
progress_msg "disabling SMT, swap, and ASLR"
# Not every machine exposes SMT control; the rest applies regardless.
if [ -e "$SMT_CONTROL" ]; then
	echo off | sudo tee "$SMT_CONTROL" > /dev/null
fi
sudo swapoff -a
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space > /dev/null

# The driver writes its records directly into results/gc and only runs
# configurations missing from them.
run_gc_bench() {
	sudo env MMTK_BPF_SHIM="$MMTK_BPF_SHIM" \
		python3 -u "$GC_PATH/scripts/run_gc_bench.py" \
		--jdk "$GC_JDK" --dacapo "$GC_DACAPO" \
		--out-dir "$RESULTS_PATH" \
		--iterations "$DACAPO_ITERS" \
		--invocations "$ITERATIONS" \
		"$@" 2>&1 \
		| filter_progress 'Running config: ' 's/.*Running config: //'
}

# h2 first: it carries the headline numbers and by far the longest runtime.
for spec in $COMPACTION; do
	run_gc_bench --klass B --bench "${spec%%:*}" --heap "${spec##*:}" \
		--configs "$COMPACTION_CONFIGS" --pauses \
		--timeout "${TIMEOUT:-1800}"
done

for bench in $TRACKING; do
	run_gc_bench --klass A --bench "$bench" --heap "$TRACKING_HEAP" \
		--configs "$TRACKING_CONFIGS" --timeout "${TIMEOUT:-900}"
done

progress_done
