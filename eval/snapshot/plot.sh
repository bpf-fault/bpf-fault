#!/bin/bash
# Firecracker snapshot plot script (Figures 6, 8, and 9)
set -eu -o pipefail

SCRIPT_PATH=$(realpath $0)
BASE_DIR=$(realpath "$(dirname $SCRIPT_PATH)/../../")
RESULTS_PATH="$BASE_DIR/results"
FIGURES_PATH="$BASE_DIR/figures"

# Figure 8 panels are the timeseries plots for this workload and memory size
FIG8_WORKLOAD="${FIG8_WORKLOAD:-redis_heavy}"
FIG8_MEM="${FIG8_MEM:-8192}"

mkdir -p "$FIGURES_PATH"

# Per-workload detail plots (phase breakdowns, timeseries, tail latency)
for json in "$RESULTS_PATH"/snapshot_benchmark_*.json; do
	if [[ ! -e "$json" ]]; then
		echo "No snapshot results in $RESULTS_PATH"
		exit 1
	fi
	wl=$(basename "$json" .json)
	python3 "$BASE_DIR/bench/plot_snapshot_benchmark.py" "$json" \
		--outdir "$FIGURES_PATH/$wl"
done

# Figure 6: snapshot downtime and total snapshot time
python3 "$BASE_DIR/bench/plot_graphs12.py" \
	--results-dir "$RESULTS_PATH" \
	--out-dir "$FIGURES_PATH" \
	--mem-sizes 4096 8192 --no-qemu \
	--output-downtime figure6a.pdf \
	--output-total figure6b.pdf

# Figure 8: Redis throughput and tail latency while taking a snapshot
FIG8_PATH="$FIGURES_PATH/snapshot_benchmark_$FIG8_WORKLOAD"
cp "$FIG8_PATH/timeseries_${FIG8_MEM}mib_full.pdf"     "$FIGURES_PATH/figure8a.pdf"
cp "$FIG8_PATH/timeseries_${FIG8_MEM}mib_live.pdf"     "$FIGURES_PATH/figure8b.pdf"
cp "$FIG8_PATH/timeseries_${FIG8_MEM}mib_live_bpf.pdf" "$FIGURES_PATH/figure8c.pdf"

# Figure 9: throughput and latency while the VM runs with snapshot WP active
python3 "$BASE_DIR/bench/plot_graph4.py" \
	--results-dir "$RESULTS_PATH" \
	--out-dir "$FIGURES_PATH" \
	--fc-mems 4096 8192 --no-qemu \
	--output-throughput figure9a.pdf \
	--output-latency figure9b.pdf

echo "Figures saved to $FIGURES_PATH"
