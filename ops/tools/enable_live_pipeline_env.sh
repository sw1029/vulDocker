#!/usr/bin/env bash
# Enable live (non-stub) LLM + remote search settings for the current shell.
# Usage:
#   source ./ops/tools/enable_live_pipeline_env.sh --web-provider tavily --web-api-key "$VUL_WEB_SEARCH_API_KEY"
#   source ./ops/tools/enable_live_pipeline_env.sh --web-provider custom --web-endpoint https://search.example/api

set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "[ENV] This script must be sourced to affect the current shell." >&2
  echo "      source ./ops/tools/enable_live_pipeline_env.sh --web-provider <custom|tavily> [options]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_PATH="${REPO_ROOT}/config/api_keys.ini"

usage() {
  cat <<'USAGE'
Usage:
  source ./ops/tools/enable_live_pipeline_env.sh --web-provider <custom|tavily> [options]

Options:
  --web-provider <NAME>  Search provider name: custom or tavily
  --web-endpoint <URL>   Remote search endpoint URL for custom provider
  --web-base-url <URL>   Base URL for Tavily provider (default: https://api.tavily.com/search)
  --web-api-key <KEY>    API key for Tavily provider (defaults to VUL_WEB_SEARCH_API_KEY)
  --help                 Show help

Notes:
  - The script loads OpenAI/Tavily API keys from env first, then falls back to config/api_keys.ini.
  - It exports:
      OPENAI_API_KEY
      VUL_LLM_API_KEY
      VUL_WEB_SEARCH_PROVIDER
      VUL_WEB_SEARCH_ENDPOINT
      VUL_WEB_SEARCH_BASE_URL
      VUL_WEB_SEARCH_API_KEY
      VUL_LLM_ENABLED=true
      VUL_REMOTE_SEARCH_ENABLED=true
USAGE
}

WEB_PROVIDER="${VUL_WEB_SEARCH_PROVIDER:-}"
WEB_ENDPOINT="${VUL_WEB_SEARCH_ENDPOINT:-}"
WEB_BASE_URL="${VUL_WEB_SEARCH_BASE_URL:-https://api.tavily.com/search}"
WEB_API_KEY="${VUL_WEB_SEARCH_API_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-provider)
      if [[ $# -lt 2 ]]; then
        echo "[ENV] --web-provider requires a value" >&2
        return 1
      fi
      WEB_PROVIDER="$2"
      shift 2
      ;;
    --web-endpoint)
      if [[ $# -lt 2 ]]; then
        echo "[ENV] --web-endpoint requires a value" >&2
        return 1
      fi
      WEB_ENDPOINT="$2"
      shift 2
      ;;
    --web-base-url)
      if [[ $# -lt 2 ]]; then
        echo "[ENV] --web-base-url requires a value" >&2
        return 1
      fi
      WEB_BASE_URL="$2"
      shift 2
      ;;
    --web-api-key)
      if [[ $# -lt 2 ]]; then
        echo "[ENV] --web-api-key requires a value" >&2
        return 1
      fi
      WEB_API_KEY="$2"
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

if [[ -z "${WEB_PROVIDER}" ]]; then
  echo "[ENV] Missing provider. Provide --web-provider <custom|tavily>." >&2
  return 1
fi
WEB_PROVIDER="$(printf '%s' "${WEB_PROVIDER}" | tr '[:upper:]' '[:lower:]')"
if [[ "${WEB_PROVIDER}" != "custom" && "${WEB_PROVIDER}" != "tavily" ]]; then
  echo "[ENV] Unsupported provider: ${WEB_PROVIDER}. Use custom or tavily." >&2
  return 1
fi
if [[ "${WEB_PROVIDER}" == "custom" && -z "${WEB_ENDPOINT}" ]]; then
  echo "[ENV] custom provider requires --web-endpoint <URL>." >&2
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

if [[ "${WEB_PROVIDER}" == "tavily" && -z "${WEB_API_KEY}" ]]; then
  if [[ -f "${CONFIG_PATH}" ]]; then
    WEB_API_KEY="$(python - <<'PY' "${CONFIG_PATH}"
import configparser
import sys
from pathlib import Path

path = Path(sys.argv[1])
parser = configparser.ConfigParser()
parser.read(path, encoding="utf-8")
print((parser.get("tavily", "api_key", fallback="") or "").strip(), end="")
PY
)"
  fi
fi

if [[ "${WEB_PROVIDER}" == "tavily" && -z "${WEB_API_KEY}" ]]; then
  echo "[ENV] tavily provider requires --web-api-key <KEY>, VUL_WEB_SEARCH_API_KEY, or config/api_keys.ini [tavily]." >&2
  return 1
fi

export OPENAI_API_KEY="${API_KEY}"
export VUL_LLM_API_KEY="${API_KEY}"
export VUL_WEB_SEARCH_PROVIDER="${WEB_PROVIDER}"
export VUL_WEB_SEARCH_ENDPOINT="${WEB_ENDPOINT}"
export VUL_WEB_SEARCH_BASE_URL="${WEB_BASE_URL}"
export VUL_WEB_SEARCH_API_KEY="${WEB_API_KEY}"
export VUL_LLM_ENABLED="true"
export VUL_REMOTE_SEARCH_ENABLED="true"

echo "[ENV] Enabled live pipeline env for current shell."
echo "[ENV] VUL_WEB_SEARCH_PROVIDER=${VUL_WEB_SEARCH_PROVIDER}"
echo "[ENV] VUL_WEB_SEARCH_ENDPOINT=${VUL_WEB_SEARCH_ENDPOINT}"
echo "[ENV] VUL_WEB_SEARCH_BASE_URL=${VUL_WEB_SEARCH_BASE_URL}"
if [[ -n "${VUL_WEB_SEARCH_API_KEY}" ]]; then
  echo "[ENV] VUL_WEB_SEARCH_API_KEY exported (value hidden)"
fi
echo "[ENV] OPENAI_API_KEY/VUL_LLM_API_KEY exported (value hidden)"
