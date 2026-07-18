#!/usr/bin/env bash
# claude_loop.sh -- headless build loop for Paper Atlas's queue.json.
#
# Walks data/queue.json and, for each iteration, invokes `claude -p` to run the
# next paper (Procedure A in CLAUDE.md: build the explainer, update the graph,
# grow the queue, remove the processed entry). It stops the moment anything is
# off: a nonzero claude exit, a hung run past --timeout, a failing build or
# lint gate, a working tree the run left dirty, or a run that made no queue
# progress. That last guard is what keeps an unattended loop from spinning
# forever on one item, and it is why the loop measures progress as the queue
# *shrinking* (Procedure A removes the processed entry every run) rather than
# trusting the run's own exit code alone.
#
# This replaces the previous version of this script, which ran 1000 iterations
# with --dangerously-skip-permissions and no gates at all (see CRITIQUE.md M-11).
#
# Usage:
#   ./claude_loop.sh [-a] [-n N] [options]
#
#   -a, --all            run until the queue is drained (default)
#   -n, --count N        run at most N items, then stop
#   -m, --model MODEL    model passed to claude    (default: claude-opus-4-8[1m])
#   -p, --prompt TEXT    per-item prompt           (default: "Run the next one.")
#   -q, --queue PATH     queue file to read        (default: data/queue.json)
#   -t, --timeout SEC    kill a single claude run after SEC seconds (needs `timeout`
#                        or `gtimeout`; default: 0 = no limit)
#       --skip-permissions  pass --dangerously-skip-permissions to claude (off by
#                           default; an unattended loop with file-write access
#                           to the whole repo is a real blast radius — opt in)
#       --no-build       skip the `npm run build` gate (not recommended)
#       --no-lint        skip the `python3 scripts/lint_pages.py` gate (not recommended)
#       --allow-dirty    do not require a clean git working tree
#       --dry-run        print the resolved plan and command, then run nothing
#   -y, --yes            do not ask for confirmation before an unbounded run
#   -h, --help           show this help and exit
#
# Exit status: 0 when the requested work finished cleanly (queue drained or the
# -n limit reached); 1 when the loop stopped for review; 2 on a usage error;
# 130 on an interrupt.

set -uo pipefail

# --- defaults ---------------------------------------------------------------
MODEL='claude-opus-4-8[1m]'
QUEUE='data/queue.json'
PROMPT='Run the next one.'
PROMPT_SET=0
SKIP_PERMISSIONS=0
RUN_BUILD=1
RUN_LINT=1
ALLOW_DIRTY=0
DRY_RUN=0
ASSUME_YES=0
TIMEOUT=0
TIMEOUT_BIN=''
MAX=''

usage() { sed -n '2,/^# Exit status/{/^# Exit status/d;s/^# \{0,1\}//;p;}' "$0"; }

die() { printf '\033[31m%s\033[0m\n' "claude_loop: $*" >&2; exit 2; }

parse_count() {
  # NOTE: this is invoked as `X="$(parse_count ...)"` — a command substitution
  # runs in a subshell, so calling die() (which does `exit`) here would only
  # kill that subshell, not the script. Print to stderr and return 1 instead;
  # every call site below checks the exit status itself and dies at top level.
  local flag="$1" val="$2"
  case "$val" in
    ''|*[!0-9]*) printf '\033[31m%s\033[0m\n' "claude_loop: $flag needs a positive integer, got '$val'" >&2; return 1 ;;
  esac
  if [ "${#val}" -gt 9 ]; then
    printf '\033[31m%s\033[0m\n' "claude_loop: $flag value '$val' is out of range" >&2; return 1
  fi
  local n=$((10#$val))
  if [ "$n" -lt 1 ]; then
    printf '\033[31m%s\033[0m\n' "claude_loop: $flag must be at least 1" >&2; return 1
  fi
  printf '%s' "$n"
}

# --- parse args -------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    -a|--all)             MAX=''; shift ;;
    -n|--count)           [ $# -ge 2 ] || die "$1 needs a value"; MAX="$(parse_count "$1" "$2")" || exit 2; shift 2 ;;
    -m|--model)           [ $# -ge 2 ] || die "$1 needs a value"; MODEL="$2"; shift 2 ;;
    -p|--prompt)          [ $# -ge 2 ] || die "$1 needs a value"; PROMPT="$2"; PROMPT_SET=1; shift 2 ;;
    -q|--queue)           [ $# -ge 2 ] || die "$1 needs a value"; QUEUE="$2"; shift 2 ;;
    -t|--timeout)         [ $# -ge 2 ] || die "$1 needs a value"; TIMEOUT="$(parse_count "$1" "$2")" || exit 2; shift 2 ;;
    --skip-permissions)   SKIP_PERMISSIONS=1; shift ;;
    --no-build)           RUN_BUILD=0; shift ;;
    --no-lint)            RUN_LINT=0; shift ;;
    --allow-dirty)        ALLOW_DIRTY=1; shift ;;
    --dry-run)            DRY_RUN=1; shift ;;
    -y|--yes)             ASSUME_YES=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    --)                   shift; break ;;
    -*)                   die "unknown option '$1' (try --help)" ;;
    *)                    die "unexpected argument '$1' (try --help)" ;;
  esac
done
[ $# -eq 0 ] || die "unexpected argument(s): $* (try --help)"

# --- move to the repo root (this script lives there) ------------------------
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || die "cannot resolve script directory"
cd "$SCRIPT_DIR" || die "cannot cd to $SCRIPT_DIR"

# --- preflight --------------------------------------------------------------
[ -f "$QUEUE" ] || die "queue file not found: $QUEUE (pass --queue if it moved)"
[ -r "$QUEUE" ] || die "queue file is not readable: $QUEUE"
command -v claude >/dev/null 2>&1 || die "the 'claude' CLI is not on PATH"
command -v python3 >/dev/null 2>&1 || die "'python3' is not on PATH"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$QUEUE" 2>/dev/null \
  || die "$QUEUE is not valid JSON"
if [ "$RUN_BUILD" -eq 1 ]; then
  command -v npm >/dev/null 2>&1 || die "'npm' is not on PATH (needed for the build gate; pass --no-build to skip)"
fi
if [ "$TIMEOUT" -gt 0 ]; then
  if command -v timeout >/dev/null 2>&1; then TIMEOUT_BIN=timeout
  elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_BIN=gtimeout
  else die "--timeout needs 'timeout' or 'gtimeout' on PATH (brew install coreutils)"; fi
fi

HAVE_GIT=0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && HAVE_GIT=1
tree_dirty() { [ -n "$(git status --porcelain 2>/dev/null)" ]; }

if [ "$HAVE_GIT" -eq 1 ] && [ "$ALLOW_DIRTY" -eq 0 ] && tree_dirty; then
  die "working tree has uncommitted changes. Commit or stash them first, or pass --allow-dirty."
fi

# --- counting helpers ---------------------------------------------------
queue_len() { python3 -c "import json; print(len(json.load(open('$QUEUE'))))" 2>/dev/null || echo -1; }

# --- build the claude command ----------------------------------------------
CLAUDE_ARGS=( -p "$PROMPT" --model "$MODEL" )
[ "$SKIP_PERMISSIONS" -eq 1 ] && CLAUDE_ARGS+=( --dangerously-skip-permissions )

# --- announce the plan ------------------------------------------------------
pending_now="$(queue_len)"
limit_desc="all ($pending_now queued)"
[ -n "$MAX" ] && limit_desc="up to $MAX (of $pending_now queued)"

printf '\033[1m%s\033[0m\n' "claude_loop plan"
printf '  queue:      %s\n' "$QUEUE"
printf '  items:      %s\n' "$limit_desc"
printf '  model:      %s\n' "$MODEL"
printf '  permissions:%s\n' "$([ "$SKIP_PERMISSIONS" -eq 1 ] && echo ' --dangerously-skip-permissions' || echo ' interactive (default)')"
printf '  timeout:    %s\n' "$([ "$TIMEOUT" -gt 0 ] && echo "${TIMEOUT}s per item (${TIMEOUT_BIN})" || echo 'none')"
printf '  gates:      %s\n' "$([ "$RUN_BUILD" -eq 1 ] && echo -n 'npm run build ' ; [ "$RUN_LINT" -eq 1 ] && echo -n 'scripts/lint_pages.py '; echo 'clean-tree queue-progress')"
printf '  command:    claude %s\n' "$(printf '%q ' "${CLAUDE_ARGS[@]}")"

if [ "$DRY_RUN" -eq 1 ]; then
  printf '\n\033[33m%s\033[0m\n' "dry run: nothing was executed."
  exit 0
fi

if [ "$pending_now" -eq 0 ]; then
  printf '\n%s\n' "queue is empty; nothing to do."
  exit 0
fi

if [ -z "$MAX" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  printf '\n%s ' "About to run ALL $pending_now item(s). Continue? [y/N]"
  read -r reply
  case "$reply" in [Yy]|[Yy][Ee][Ss]) ;; *) echo "aborted."; exit 0 ;; esac
fi

# --- signal handling and the claude runner ----------------------------------
CHILD_PID=''
on_signal() {
  printf '\n\033[33m%s\033[0m\n' "claude_loop: interrupted; stopping."
  if [ -n "$CHILD_PID" ]; then
    kill -TERM "$CHILD_PID" 2>/dev/null
    wait "$CHILD_PID" 2>/dev/null
  fi
  exit 130
}
trap on_signal INT TERM

run_claude() {
  if [ "$TIMEOUT" -gt 0 ]; then
    "$TIMEOUT_BIN" "$TIMEOUT" claude "${CLAUDE_ARGS[@]}" </dev/null &
  else
    claude "${CLAUDE_ARGS[@]}" </dev/null &
  fi
  CHILD_PID=$!
  wait "$CHILD_PID"
  local rc=$?
  CHILD_PID=''
  return "$rc"
}

# --- the loop ---------------------------------------------------------------
i=0
while :; do
  pending="$(queue_len)"
  if [ "$pending" -eq 0 ]; then
    printf '\n\033[32m%s\033[0m\n' "queue drained. Ran $i item(s)."
    break
  fi
  if [ -n "$MAX" ] && [ "$i" -ge "$MAX" ]; then
    printf '\n\033[32m%s\033[0m\n' "reached limit of $MAX item(s). $pending still queued."
    break
  fi

  before="$pending"
  i=$((i + 1))
  printf '\n\033[1m\033[36m==== item %d  (%s, %s queued) ====\033[0m\n' "$i" "$(date '+%Y-%m-%d %H:%M:%S')" "$pending"

  run_claude; claude_rc=$?
  if [ "$claude_rc" -ne 0 ]; then
    if [ "$TIMEOUT" -gt 0 ] && [ "$claude_rc" -eq 124 ]; then
      printf '\n\033[31m%s\033[0m\n' "claude exceeded the ${TIMEOUT}s timeout on item $i; stopping for review."
    else
      printf '\n\033[31m%s\033[0m\n' "claude exited $claude_rc on item $i; stopping for review."
    fi
    exit 1
  fi

  if [ "$HAVE_GIT" -eq 1 ] && [ "$ALLOW_DIRTY" -eq 0 ] && tree_dirty; then
    printf '\n\033[33m%s\033[0m\n' "item $i left uncommitted changes (expected — CLAUDE.md says never auto-commit). Review before continuing."
  fi

  if [ "$RUN_BUILD" -eq 1 ]; then
    if ! npm run build >/tmp/claude_loop_build.log 2>&1; then
      printf '\n\033[31m%s\033[0m\n' "npm run build failed after item $i; stopping for review (see /tmp/claude_loop_build.log)."
      exit 1
    fi
  fi

  if [ "$RUN_LINT" -eq 1 ]; then
    if ! python3 scripts/lint_pages.py >/tmp/claude_loop_lint.log 2>&1; then
      printf '\n\033[31m%s\033[0m\n' "scripts/lint_pages.py failed after item $i; stopping for review (see /tmp/claude_loop_lint.log)."
      exit 1
    fi
  fi

  after="$(queue_len)"
  if [ "$after" -ge "$before" ]; then
    printf '\n\033[31m%s\033[0m\n' "no queue progress on item $i (queue did not shrink); stopping to avoid an infinite loop."
    exit 1
  fi
done

exit 0
