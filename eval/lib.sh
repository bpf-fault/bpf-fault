# Shared style and progress helpers for the eval and install scripts.
# Sourced, not run.
#
# Two display modes:
#   - progress_* (run/plot scripts): a compact two-line display, redrawn
#     in place on a TTY —
#         <name>: in progress [<step>/<total>] · <elapsed>
#           ▶ <current step>
#   - checklist_* (install scripts): one permanent line per step; only
#     the in-progress line is redrawn, then finalized in place.
#
# In both, raw tool output goes to a log file instead of the terminal.
# Set VERBOSE=1 to stream it through (disables the live display). On a
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
	local first=1 count reused msg width left pad
	while :; do
		{ read -r count; read -r reused; read -r msg; } < "$_P_STATE"
		width=$(tput cols 2>/dev/null </dev/tty || echo 80)
		[ "$first" = 1 ] || printf '\033[2A'
		first=0
		# Show the log path while running, in the same column as the
		# completion line; drop it when the terminal is too narrow.
		left="  ${_P_PREFIX}${_P_NAME}: in progress [${count}/${_P_TOTAL}] · $(_progress_elapsed)"
		pad=$((68 - ${#left}))
		[ "$pad" -lt 3 ] && pad=3
		if [ $((${#left} + pad + ${#_P_LOG} + 7)) -le "$width" ]; then
			printf '\r%s%*s%s\033[K\n' \
				"${BOLD}${left}${RESET}" "$pad" "" "${DIM}(log: $_P_LOG)${RESET}"
		else
			_progress_line "$left" "$BOLD" "$width"
		fi
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

# ---------------------------------------------------------------------------
# Checklist mode (install scripts)
#
# One permanent line per step; only the in-progress line is redrawn (for
# the elapsed time), then finalized in place:
#
#     <name>: 8 steps (log: ...)
#     ✓ [1/8] install build dependencies                       (0m 42s)
#     ▶ [2/8] build and install kernel · 12m 04s
#
# Usage:
#     checklist_init "install_kernel" 8 "$BASE_DIR/results/logs/install-kernel.log"
#     checklist_step "install build dependencies" install_deps
#     checklist_skip "initialize linux submodule" "already checked out"
#     long_setup 2>&1 | checklist_filter '^Building' 's/^Building //'
#     checklist_done "To boot into the kernel: sudo reboot now"
# ---------------------------------------------------------------------------

# Duration column: the "✓ [k/N] description" text is padded to this width
_CL_PAD=58

# Print a finalized checklist line, replacing the in-progress line on a
# TTY (plain append otherwise).
_cl_final_line() {
	if [ "$_LIVE" = 1 ]; then
		printf '\r%s\033[K\n' "$1"
	else
		printf '%s\n' "$1"
	fi
}

_cl_fmt_dur() {
	local s="$1"
	if [ "$s" -ge 3600 ]; then
		printf '%dh %02dm' $((s / 3600)) $((s % 3600 / 60))
	else
		printf '%dm %02ds' $((s / 60)) $((s % 60))
	fi
}

# checklist_init <name> <total-steps> <log-file>
checklist_init() {
	# Run the last stage of pipelines in this shell, not a subshell, so
	# checklist_filter's step counters survive into checklist_done.
	shopt -s lastpipe
	_CL_NAME="$1"
	_CL_TOTAL="$2"
	_CL_LOG="$3"
	_CL_START=$(date +%s)
	_CL_COUNT=0
	_CL_SKIPPED=0
	_CL_CUR=""
	_CL_MSG=""
	_CL_DONE=0
	mkdir -p "$(dirname "$_CL_LOG")"
	# Same concurrency guard as progress_init
	exec 9> "$_CL_LOG.lock"
	if ! flock -n 9; then
		die "another '$_CL_NAME' run is already in progress"$'\n'"(close it first, or remove a stale $_CL_LOG.lock)"
	fi
	: > "$_CL_LOG"
	trap _checklist_exit EXIT
	printf '%s\n' "  ${BOLD}${_CL_NAME}${RESET}: ${_CL_TOTAL} steps ${DIM}(log: $_CL_LOG)${RESET}"
}

# Repaint the in-progress line (no newline; truncated to terminal width)
_cl_paint() {
	[ "$_LIVE" = 1 ] || return 0
	local text="  ▶ [${_CL_COUNT}/${_CL_TOTAL}] ${_CL_CUR}${_CL_MSG:+ — ${_CL_MSG}} · $(_cl_fmt_dur $(( $(date +%s) - _CL_STEP_START )))"
	local width=$(tput cols 2>/dev/null </dev/tty || echo 80)
	if [ "${#text}" -gt "$width" ]; then
		text="${text:0:$((width - 1))}…"
	fi
	printf '\r%s\033[K' "$text"
}

# Begin an in-progress step
_cl_open() {
	_CL_COUNT=$((_CL_COUNT + 1))
	_CL_CUR="$1"
	_CL_MSG=""
	_CL_STEP_START=$(date +%s)
	if [ "$_LIVE" = 1 ]; then
		_cl_paint
	else
		printf '%s\n' "  ▶ [${_CL_COUNT}/${_CL_TOTAL}] ${_CL_CUR}"
	fi
}

# Finalize the in-progress step as completed
_cl_close_ok() {
	[ -n "$_CL_CUR" ] || return 0
	local plain="✓ [${_CL_COUNT}/${_CL_TOTAL}] ${_CL_CUR}"
	local pad=$((_CL_PAD - ${#plain}))
	[ "$pad" -lt 2 ] && pad=2
	_cl_final_line "$(printf '  %s%*s%s' \
		"${GREEN}✓${RESET} [${_CL_COUNT}/${_CL_TOTAL}] ${_CL_CUR}" \
		"$pad" "" "${DIM}($(_cl_fmt_dur $(( $(date +%s) - _CL_STEP_START ))))${RESET}")"
	_CL_CUR=""
	_CL_MSG=""
}

# checklist_skip <description> <reason> — permanent line for a step whose
# work is already done (e.g. a tool that is already installed).
checklist_skip() {
	_CL_COUNT=$((_CL_COUNT + 1))
	_CL_SKIPPED=$((_CL_SKIPPED + 1))
	local plain="✓ [${_CL_COUNT}/${_CL_TOTAL}] $1"
	local pad=$((_CL_PAD - ${#plain}))
	[ "$pad" -lt 2 ] && pad=2
	_cl_final_line "$(printf '  %s%*s%s' \
		"${GREEN}✓${RESET} [${_CL_COUNT}/${_CL_TOTAL}] $1" \
		"$pad" "" "${DIM}(skipped: $2)${RESET}")"
}

# Finalize the in-progress step as failed, show the log tail, and exit
_cl_fail() {
	local rc="$1"
	_cl_final_line \
		"  ${RED}✗ [${_CL_COUNT}/${_CL_TOTAL}] ${_CL_CUR} failed after $(_cl_fmt_dur $(( $(date +%s) - _CL_STEP_START )))${RESET}"
	tail -10 "$_CL_LOG" | sed "s/^/      ${DIM}│${RESET} /"
	printf '%s\n' "  ${DIM}full log: $_CL_LOG${RESET}"
	_CL_DONE=1
	exit "$rc"
}

# checklist_step <description> <command...> — run the command with its
# output in the log, showing a live elapsed time; finalize the line as
# completed or failed. Compound steps go in a shell function.
checklist_step() {
	local desc="$1" rc=0
	shift
	_cl_open "$desc"
	if [ "${VERBOSE:-0}" = 1 ]; then
		printf '\n'
		"$@" 2>&1 | tee -a "$_CL_LOG" || rc=$?
	elif [ "$_LIVE" = 1 ]; then
		"$@" >> "$_CL_LOG" 2>&1 &
		local pid=$!
		while kill -0 "$pid" 2>/dev/null; do
			_cl_paint
			sleep 0.5
		done
		wait "$pid" || rc=$?
	else
		"$@" >> "$_CL_LOG" 2>&1 || rc=$?
	fi
	[ "$rc" -eq 0 ] || _cl_fail "$rc"
	_cl_close_ok
}

# checklist_filter [-M <ere-pattern> <sed-script>] <ere-pattern> <sed-script>
# Stream-driven steps: log every stdin line; a line matching the pattern
# finalizes the current step and starts a new one described by the line
# run through the sed script (lines containing "Skipping" finalize as
# skipped steps instead). -M lines update the in-progress description.
# A repeated step description (e.g. after the producer re-execs itself)
# is ignored rather than double-counted.
checklist_filter() {
	local msgpat="" msgsed=""
	if [ "${1:-}" = "-M" ]; then
		msgpat="$2"
		msgsed="$3"
		shift 3
	fi
	local pat="$1" sedscript="$2" line desc seen=""
	while :; do
		if IFS= read -r -t 1 line; then
			printf '%s\n' "$line" >> "$_CL_LOG"
			if [ "${VERBOSE:-0}" = 1 ]; then
				printf '%s\n' "$line"
			fi
			if [[ $line =~ $pat ]]; then
				desc=$(printf '%s\n' "$line" | sed -E "$sedscript")
				case "$seen" in *"|$desc|"*) continue ;; esac
				seen="$seen|$desc|"
				_cl_close_ok
				if [[ $line == *Skipping* ]]; then
					checklist_skip "$desc" "already done"
				else
					_cl_open "$desc"
				fi
			elif [ -n "$msgpat" ] && [[ $line =~ $msgpat ]]; then
				_CL_MSG=$(printf '%s\n' "$line" | sed -E "$msgsed")
				_cl_paint
			fi
		else
			[ $? -gt 128 ] || break
			[ -n "$_CL_CUR" ] && _cl_paint
		fi
	done
	# Leave any in-progress step open: if the producer failed, the exit
	# trap reports it as the failing step; checklist_done closes it on
	# success.
	return 0
}

# checklist_done [note] — print the completion line; the optional note
# goes on a dim second line.
checklist_done() {
	_cl_close_ok
	_CL_DONE=1
	local note="${1:-}" extra=""
	[ "$_CL_SKIPPED" -gt 0 ] && extra=" (${_CL_SKIPPED} skipped)"
	printf '%s\n' \
		"${GREEN}✓${RESET} ${BOLD}${_CL_NAME}${RESET} [${_CL_COUNT}/${_CL_TOTAL}] completed in $(_cl_fmt_dur $(( $(date +%s) - _CL_START )))${extra}"
	if [ -n "$note" ]; then
		printf '%s\n' "  ${DIM}${note}${RESET}"
	fi
}

_checklist_exit() {
	[ "${_CL_DONE:-1}" = 1 ] && return 0
	_cl_final_line \
		"${RED}✗ ${_CL_NAME} failed at step ${_CL_COUNT}/${_CL_TOTAL}${_CL_CUR:+ (${_CL_CUR})} after $(_cl_fmt_dur $(( $(date +%s) - _CL_START )))${RESET}"
	tail -10 "$_CL_LOG" 2>/dev/null | sed "s/^/      ${DIM}│${RESET} /"
	printf '%s\n' "  ${DIM}full log: $_CL_LOG${RESET}"
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
