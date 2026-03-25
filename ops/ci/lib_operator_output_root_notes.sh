#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_output_notes.sh"

operator_emit_output_root_children() {
  local log_prefix="$1"
  local output_root="$2"
  shift 2

  if (($# % 2 != 0)); then
    echo "[${log_prefix}] output-root child pairs are required" >&2
    return 1
  fi

  local resolved_pairs=()
  while (($# >= 2)); do
    resolved_pairs+=("$1" "${output_root}/$2")
    shift 2
  done

  operator_emit_completion_and_outputs "${log_prefix}" "${resolved_pairs[@]}"
}
