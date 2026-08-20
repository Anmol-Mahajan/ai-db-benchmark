#!/usr/bin/env bash
set -euo pipefail

docker compose down

if [[ "${1:-}" == "--ollama" || "${1:-}" == "--all" ]]; then
  osascript -e 'quit app "Ollama"' >/dev/null 2>&1 || true
  pkill -TERM -f '/Applications/Ollama.app' >/dev/null 2>&1 || true
fi
