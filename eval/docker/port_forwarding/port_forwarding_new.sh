#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../../config/.env"

SERVER="${1:-}"
if [[ -z "$SERVER" ]] && [[ -f "$ENV_FILE" ]]; then
  SERVER=$(grep -E '^REMOTE_HOST=' "$ENV_FILE" | head -1 | cut -d= -f2-)
fi
if [[ -z "$SERVER" ]]; then
  echo "Error: no server specified. Pass user@host as an argument or set REMOTE_HOST in config/.env." >&2
  exit 1
fi
ORCH="/scr2/webagent-verified/webarena_orchestrator/orchestrator.py"
TOTAL_WORKERS=$(ssh "$SERVER" python3 "$ORCH" num_workers)

FORWARD_SHOPPING=true
FORWARD_ADMIN=true
FORWARD_REDDIT=true
FORWARD_GITLAB=true

CMD=(ssh -N)

for WORKER_ID in $(seq 1 "$TOTAL_WORKERS"); do
  BASE=$((20000 + WORKER_ID * 10))
  SHOPPING_REMOTE=$((BASE + 0))
  ADMIN_REMOTE=$((BASE + 2))
  REDDIT_REMOTE=$((BASE + 4))
  GITLAB_REMOTE=$((BASE + 6))

  if $FORWARD_SHOPPING; then
    CMD+=(-L "${SHOPPING_REMOTE}:127.0.0.1:${SHOPPING_REMOTE}")
  fi

  if $FORWARD_ADMIN; then
    CMD+=(-L "${ADMIN_REMOTE}:127.0.0.1:${ADMIN_REMOTE}")
  fi

  if $FORWARD_REDDIT; then
    CMD+=(-L "${REDDIT_REMOTE}:127.0.0.1:${REDDIT_REMOTE}")
  fi

  if $FORWARD_GITLAB; then
    CMD+=(-L "${GITLAB_REMOTE}:127.0.0.1:${GITLAB_REMOTE}")
  fi
done

CMD+=("$SERVER")

exec "${CMD[@]}"

  #ex: ./port_forwarding_new.sh username@red5k.cs.berkeley.edu