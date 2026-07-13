# Shared style and progress helpers for the eval scripts. Sourced, not run.
#
# Scripts drive a compact two-line display, redrawn in place on a TTY:
#
#     <name>: in progress [<step>/<total>] · <elapsed>
#       ▶ <current step>
#
# Raw tool output goes to a log file instead of the terminal. Set
# VERBOSE=1 to stream it through (disables the live display). On a
# non-TTY, the display degrades to appended plain lines.
#
# Usage:
#     . "$BASE_DIR/eval/lib.sh"
#     progress_init "efency" 76 "$BASE_DIR/results/logs/run-efency.log"
#     progress_step "building"
#     quiet make
#     long_cmd 2>&1 | filter_progress '^Running' 's/^Running //'
#     progress_done "figures: figure11a.pdf, figure11b.pdf"

# Colors when stdout is a TTY (and NO_COLOR is unset)
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
	BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[0;31m'
	GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; RESET=$'\033[0m'
	_LIVE=1
else
	BOLD=''; DIM=''; RED=''; GREEN=''; YELLOW=''; RESET=''
	_LIVE=0
fi
# VERBOSE streams raw output, which would fight the live display
if [ "${VERBOSE:-0}" = 1 ]; then
	_LIVE=0
fi

die() {
	printf '%s\n' "${RED}$*${RESET}" >&2
	exit 1
}

_progress_elapsed() {
	local s=$(( $(date +%s) - _P_START ))
	if [ "$s" -ge 3600 ]; then
		printf '%dh %02dm' $((s / 3600)) $((s % 3600 / 60))
	else
		printf '%dm %02ds' $((s / 60)) $((s % 60))
	fi
}

# Print a line truncated to the terminal width; visible length is
# computed before color so escape codes don't count. Painting over the
# old text and clearing to end-of-line afterwards (rather than clearing
# first) avoids a blank-frame flicker.
_progress_line() {
	local text="$1" color="$2" width="$3"
	if [ "${#text}" -gt "$width" ]; then
		text="${text:0:$((width - 1))}…"
	fi
	printf '\r%s\033[K\n' "${color}${text}${RESET}"
}

# Redraw loop for the live two-line display (background job on a TTY)
_progress_ticker() {
	trap 'exit 0' TERM
	local first=1 count reused msg width
	while :; do
		{ read -r count; read -r reused; read -r msg; } < "$_P_STATE"
		width=$(tput cols 2>/dev/null || echo 80)
		[ "$first" = 1 ] || printf '\033[2A'
		first=0
		_progress_line \
			"  ${_P_PREFIX}${_P_NAME}: in progress [${count}/${_P_TOTAL}] · $(_progress_elapsed)" \
			"$BOLD" "$width"
		_progress_line "    ▶ ${msg}" "" "$width"
		sleep 1
	done
}

# progress_init <name> <total-steps> <log-file>
progress_init() {
	_P_NAME="$1"
	_P_TOTAL="$2"
	_P_LOG="$3"
	_P_START=$(date +%s)
	_P_DONE=0
	_P_TICKER=""
	_P_PREFIX="${EVAL_PROGRESS_PREFIX:-}"
	mkdir -p "$(dirname "$_P_LOG")"
	# Concurrent runs of the same script share a log, results store, and
	# (for some experiments) VM artifacts; refuse rather than corrupt.
	# The lock is tied to fd 9 and releases when the script exits.
	exec 9> "$_P_LOG.lock"
	if ! flock -n 9; then
		die "another '$_P_NAME' run is already in progress"$'\n'"(close it first, or remove a stale $_P_LOG.lock)"
	fi
	: > "$_P_LOG"
	_P_STATE=$(mktemp)
	printf '0\n0\nstarting\n' > "$_P_STATE"
	trap _progress_exit EXIT
	if [ "$_LIVE" = 1 ]; then
		_progress_ticker &
		_P_TICKER=$!
	else
		printf '%s\n' "  ${_P_PREFIX}${_P_NAME}: started (log: $_P_LOG)"
	fi
}

_progress_set() {
	local step_incr="$1" reused_incr="$2" msg="$3" count reused old_msg
	{ read -r count; read -r reused; read -r old_msg; } < "$_P_STATE"
	count=$((count + step_incr))
	reused=$((reused + reused_incr))
	[ -n "$msg" ] || msg="$old_msg"
	printf '%s\n%s\n%s\n' "$count" "$reused" "$msg" > "$_P_STATE.new"
	mv -f "$_P_STATE.new" "$_P_STATE"
	if [ "$_LIVE" = 0 ] && [ "$reused_incr" = 0 ]; then
		printf '%s\n' "  ${_P_PREFIX}${_P_NAME} [${count}/${_P_TOTAL}]: ${msg}"
	fi
}

# Advance the step counter and set the current-step line
progress_step() {
	_progress_set 1 0 "$1"
}

# Update the current-step line without advancing the counter
progress_msg() {
	_progress_set 0 0 "$1"
}

# Count a unit of work skipped via result reuse: it advances the step
# counter like completed work (so [k/N] accounts for every unit) and is
# reported separately in the completion line.
progress_skip() {
	_progress_set 1 1 ""
}

_progress_stop() {
	if [ -n "$_P_TICKER" ]; then
		kill "$_P_TICKER" 2>/dev/null || true
		wait "$_P_TICKER" 2>/dev/null || true
		_P_TICKER=""
		printf '\033[2A\r\033[J'
	fi
}

# progress_done [note] — print the completion line; the optional note
# (e.g. produced figures) goes on a dim second line.
progress_done() {
	_P_DONE=1
	_progress_stop
	local note="${1:-}" count reused msg elapsed extra="" pad plain warnings
	{ read -r count; read -r reused; read -r msg; } < "$_P_STATE"
	elapsed=$(_progress_elapsed)
	[ "$reused" -gt 0 ] && extra=" (${reused} reused)"
	# Pad based on the uncolored text so the log column lines up
	plain="✓ ${_P_PREFIX}${_P_NAME} [${count}/${_P_TOTAL}] completed in ${elapsed}${extra}"
	pad=$((68 - ${#plain}))
	[ "$pad" -lt 3 ] && pad=3
	printf '%s%*s%s\n' \
		"${GREEN}✓${RESET} ${BOLD}${_P_PREFIX}${_P_NAME}${RESET} [${count}/${_P_TOTAL}] completed in ${elapsed}${extra}" \
		"$pad" "" "${DIM}(log: $_P_LOG)${RESET}"
	if [ -n "$note" ]; then
		printf '%s\n' "  ${DIM}${note}${RESET}"
	fi
	warnings=$(grep -c '^warning' "$_P_LOG" 2>/dev/null || true)
	if [ "${warnings:-0}" -gt 0 ]; then
		printf '%s\n' "  ${YELLOW}⚠ ${warnings} warning(s) — see log${RESET}"
	fi
	rm -f "$_P_STATE"
}

_progress_exit() {
	[ "${_P_DONE:-1}" = 1 ] && return 0
	_progress_stop
	local count='?' reused='' msg='?'
	{ read -r count; read -r reused; read -r msg; } < "$_P_STATE" 2>/dev/null || true
	printf '%s\n' "${RED}✗ ${_P_PREFIX}${_P_NAME} failed at step ${count}/${_P_TOTAL} (${msg}) after $(_progress_elapsed)${RESET}"
	printf '%s\n' "  ${DIM}full log: $_P_LOG${RESET}"
	rm -f "$_P_STATE"
}

# Run a command with its output appended to the log
quiet() {
	if [ "${VERBOSE:-0}" = 1 ]; then
		"$@" 2>&1 | tee -a "$_P_LOG"
	else
		"$@" >> "$_P_LOG" 2>&1
	fi
}

# filter_progress [-m] [-M <ere-pattern> <sed-script>] <ere-pattern> [sed-script]
# Log every stdin line; lines matching the pattern become progress steps
# (or, with -m, current-step updates without advancing the counter),
# optionally rewritten by the sed script first. -M adds a secondary
# pattern whose matches update the current-step line without counting
# (e.g. setup phases). Lines containing "Skipping" count as reused work.
filter_progress() {
	local update=progress_step msgpat="" msgsed=""
	while :; do
		case "${1:-}" in
		-m)
			update=progress_msg
			shift
			;;
		-M)
			msgpat="$2"
			msgsed="$3"
			shift 3
			;;
		*)
			break
			;;
		esac
	done
	local pat="$1" sedscript="${2:-}" line msg
	while IFS= read -r line; do
		printf '%s\n' "$line" >> "$_P_LOG"
		if [ "${VERBOSE:-0}" = 1 ]; then
			printf '%s\n' "$line"
		fi
		if [[ $line == *Skipping* ]]; then
			progress_skip
		elif [[ $line =~ $pat ]]; then
			msg="$line"
			if [ -n "$sedscript" ]; then
				msg=$(printf '%s\n' "$line" | sed -E "$sedscript")
			fi
			"$update" "$msg"
		elif [ -n "$msgpat" ] && [[ $line =~ $msgpat ]]; then
			progress_msg "$(printf '%s\n' "$line" | sed -E "$msgsed")"
		fi
	done
	return 0
}
