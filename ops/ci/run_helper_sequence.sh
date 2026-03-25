#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 PREFIX LABEL HELPER [ARG ...] [-- LABEL HELPER [ARG ...]] ..." >&2
  exit 1
fi

PREFIX="$1"
shift

while [[ $# -gt 0 ]]; do
  LABEL="${1:-}"
  HELPER="${2:-}"

  if [[ -z "${LABEL}" || -z "${HELPER}" ]]; then
    echo "[${PREFIX}] invalid helper sequence entry" >&2
    exit 1
  fi

  shift 2
  HELPER_ARGS=()
  while [[ $# -gt 0 && "$1" != "--" ]]; do
    HELPER_ARGS+=("$1")
    shift
  done

  if [[ $# -gt 0 && "$1" == "--" ]]; then
    shift
  fi

  if [[ ! -x "${HELPER}" ]]; then
    echo "[${PREFIX}] helper not found or not executable: ${HELPER}" >&2
    exit 1
  fi

  echo "[${PREFIX}] ${LABEL}"
  "${HELPER}" "${HELPER_ARGS[@]}"
done

echo "[${PREFIX}] completed"
