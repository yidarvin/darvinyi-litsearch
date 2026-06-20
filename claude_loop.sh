#!/usr/bin/env bash

# Pin subagents to Opus 4.8 too, so ultracode's spawned workflows run at full strength
# (by default subagents may fall back to a faster, weaker model)
export CLAUDE_CODE_SUBAGENT_MODEL='claude-opus-4-8'

TOTAL=50

for i in $(seq 1 "$TOTAL"); do
  echo "──────── Run $i / $TOTAL ────────"
  claude -p "run the next one" \
    --model 'claude-opus-4-8[1m]' \
    --settings '{"ultracode":true}' \
    --dangerously-skip-permissions
done