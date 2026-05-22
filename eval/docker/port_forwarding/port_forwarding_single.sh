#!/usr/bin/env bash
# Forward ports for a single WebArena instance from a remote machine to localhost.
# Use this for single-instance runs. For multi-docker (N workers), use port_forwarding_new.sh.
#
# Usage: ./port_forwarding_single.sh [user@hostname]
# If no argument is given, REMOTE_HOST from config/.env is used.

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

exec ssh -N \
  -L 7770:127.0.0.1:7770 \
  -L 7780:127.0.0.1:7780 \
  -L 9999:127.0.0.1:9999 \
  -L 8023:127.0.0.1:8023 \
  -L 8889:127.0.0.1:8889 \
  -L 7771:127.0.0.1:7771 \
  -L 7781:127.0.0.1:7781 \
  -L 10000:127.0.0.1:10001 \
  -L 8024:127.0.0.1:8024 \
  -L 8890:127.0.0.1:8890 \
  "$SERVER"
