#!/usr/bin/env bash
set -euo pipefail

SERVER="$1"
ORCH="/scr2/webagent/webarena_orchestrator/orchestrator.py"
TOTAL_WORKERS=$(ssh "$SERVER" python3 "$ORCH" num_workers)


FORWARD_SHOPPING=false
FORWARD_ADMIN=false
FORWARD_FORUM=false
FORWARD_GITLAB=true
FORWARD_WIKI=false

CMD=(ssh -N)

for WORKER_ID in $(seq 1 "$TOTAL_WORKERS"); do
  SHOPPING_REMOTE=$((7700 + WORKER_ID))
  ADMIN_REMOTE=$((7800 + WORKER_ID))
  FORUM_REMOTE=$((9999 + WORKER_ID))
  FORUM_REMOTE=$((9999 + WORKER_ID))
  GITLAB_REMOTE=$((8023 + WORKER_ID))
  WIKI_REMOTE=$((8880 + WORKER_ID))

  if $FORWARD_SHOPPING; then
    CMD+=(-L "${SHOPPING_REMOTE}:127.0.0.1:${SHOPPING_REMOTE}")
    CMD+=(-L "${SHOPPING_REMOTE}:127.0.0.1:${SHOPPING_REMOTE}")
  fi

  if $FORWARD_ADMIN; then
    CMD+=(-L "${ADMIN_REMOTE}:127.0.0.1:${ADMIN_REMOTE}")
  fi

  if $FORWARD_FORUM; then
    CMD+=(-L "${FORUM_REMOTE}:127.0.0.1:${FORUM_REMOTE}")
    CMD+=(-L "${FORUM_REMOTE}:127.0.0.1:${FORUM_REMOTE}")
  fi

  if $FORWARD_GITLAB; then
    CMD+=(-L "${GITLAB_REMOTE}:127.0.0.1:${GITLAB_REMOTE}")
    CMD+=(-L "${GITLAB_REMOTE}:127.0.0.1:${GITLAB_REMOTE}")
  fi

  if $FORWARD_WIKI; then
    CMD+=(-L "${WIKI_REMOTE}:127.0.0.1:${WIKI_REMOTE}")
    CMD+=(-L "${WIKI_REMOTE}:127.0.0.1:${WIKI_REMOTE}")
  fi
done

CMD+=("$SERVER")

exec "${CMD[@]}"


# exec ssh -N \
  # -L "${SHOPPING_REMOTE}:127.0.0.1:${SHOPPING_REMOTE}" \
  # -L "${ADMIN_REMOTE}:127.0.0.1:${ADMIN_REMOTE}" \
  # -L "${FORUM_REMOTE}:127.0.0.1:${FORUM_REMOTE}" \
  # -L "${GITLAB_REMOTE}:127.0.0.1:${GITLAB_REMOTE}" \
  # -L "${WIKI_REMOTE}:127.0.0.1:${WIKI_REMOTE}" \
  # "$SERVER"


  #ex: ./port_forwarding.sh username@red5k.cs.berkeley.edu