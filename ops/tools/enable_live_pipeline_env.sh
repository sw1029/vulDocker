#!/usr/bin/env bash
# Enable live (non-stub) LLM + remote search settings for the current shell.
# Usage:
#   source ./ops/tools/enable_live_pipeline_env.sh --web-endpoint https://search.example/api
#   source ./ops/tools/enable_live_pipeline_env.sh --web-endpoint "$VUL_WEB_SEARCH_ENDPOINT"

set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "[ENV] This script must be sourced to affect the current shell." >&2
  echo "      source ./ops/tools/enable_live_pipeline_env.sh --web-endpoint <URL>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_PATH="${REPO_ROOT}/config/api_keys.ini"

usage() {
  cat <<'USAGE'
Usage:
  source ./ops/tools/enable_live_pipeline_env.sh --web-endpoint <URL>

Options:
  --web-endpoint <URL>   Remote search endpoint URL for VUL_WEB_SEARCH_ENDPOINT
  --help                 Show help

Notes:
  - The script loads API key from OPENAI_API_KEY, VUL_LLM_API_KEY, or config/api_keys.ini.
  - It exports:
      OPENAI_API_KEY
      VUL_LLM_API_KEY
      VUL_WEB_SEARCH_ENDPOINT
      VUL_LLM_ENABLED=true
      VUL_REMOTE_SEARCH_ENABLED=true
USAGE
}

WEB_ENDPOINT="${VUL_WEB_SEARCH_ENDPOINT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-endpoint)
      if [[ $# -lt 2 ]]; then
        echo "[ENV] --web-endpoint requires a value" >&2
        return 1
      fi
      WEB_ENDPOINT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      return 0
      ;;
    *)
      echo "[ENV] Unknown option: $1" >&2
      usage >&2
      return 1
      ;;
  esac
done

if [[ -z "${WEB_ENDPOINT}" ]]; then
  echo "[ENV] Missing remote endpoint. Provide --web-endpoint <URL>." >&2
  return 1
fi

API_KEY="${OPENAI_API_KEY:-${VUL_LLM_API_KEY:-}}"
if [[ -z "${API_KEY}" ]]; then
  if [[ -f "${CONFIG_PATH}" ]]; then
    API_KEY="$(python - <<'PY' "${CONFIG_PATH}"
import configparser
import sys
from pathlib import Path

path = Path(sys.argv[1])
parser = configparser.ConfigParser()
parser.read(path, encoding="utf-8")
print((parser.get("openai", "api_key", fallback="") or "").strip(), end="")
PY
)"
  fi
fi

if [[ -z "${API_KEY}" ]]; then
  echo "[ENV] OpenAI API key not found in env or ${CONFIG_PATH}" >&2
  return 1
fi

export OPENAI_API_KEY="${API_KEY}"
export VUL_LLM_API_KEY="${API_KEY}"
export VUL_WEB_SEARCH_ENDPOINT="${WEB_ENDPOINT}"
export VUL_LLM_ENABLED="true"
export VUL_REMOTE_SEARCH_ENABLED="true"

echo "[ENV] Enabled live pipeline env for current shell."
echo "[ENV] VUL_WEB_SEARCH_ENDPOINT=${VUL_WEB_SEARCH_ENDPOINT}"
echo "[ENV] OPENAI_API_KEY/VUL_LLM_API_KEY exported (value hidden)"
