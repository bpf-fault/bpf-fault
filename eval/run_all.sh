#!/bin/bash
# Run every experiment, then generate every figure. A failure in one
# script does not stop the others; a summary is printed at the end.
# No -e: per-script failures are handled explicitly.
set -u -o pipefail

SCRIPT_PATH=$(realpath $0)
EVAL_DIR=$(dirname $SCRIPT_PATH)
BASE_DIR=$(realpath "$EVAL_DIR/..")

. "$EVAL_DIR/lib.sh"

# Ordered by expected runtime, shortest first
EXPERIMENTS="fault-latency scalability efency snapshot dynlink"
set -- $EXPERIMENTS
TOTAL=$(($# * 2))

printf '%s\n\n' "${BOLD}bpf_fault artifact evaluation — $# experiments${RESET}"

trap 'printf "\n%s\n" "${RED}Interrupted.${RESET}"; exit 130' INT

FAILURES=""
STEP=0

run_step() {
	local phase="$1" exp="$2" rc
	STEP=$((STEP + 1))
	EVAL_PROGRESS_PREFIX="[$STEP/$TOTAL] " "$EVAL_DIR/$exp/$phase.sh"
	rc=$?
	if [ "$rc" -eq 130 ]; then
		printf '\n%s\n' "${RED}Interrupted.${RESET}"
		exit 130
	elif [ "$rc" -ne 0 ]; then
		FAILURES="$FAILURES $phase:$exp"
		tail -n 15 "$BASE_DIR/results/logs/$phase-$exp.log" 2>/dev/null \
			| sed "s/^/      ${DIM}│${RESET} /"
	fi
}

for exp in $EXPERIMENTS; do
	run_step run "$exp"
done

for exp in $EXPERIMENTS; do
	run_step plot "$exp"
done

echo ""
if [ -n "$FAILURES" ]; then
	printf '%s\n' "${RED}${BOLD}The following steps failed:${RESET}"
	for failure in $FAILURES; do
		printf '  %s\n' "${RED}✗ $failure${RESET}"
	done
	exit 1
fi
printf '%s\n' "${GREEN}${BOLD}All experiments and figures completed; figures are in $BASE_DIR/figures${RESET}"
