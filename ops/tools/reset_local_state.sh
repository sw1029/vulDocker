#!/usr/bin/env bash
# Reset metadata, workspace outputs, artifacts, and RAG memories to a clean slate.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "error: could not find repo root from $SCRIPT_DIR" >&2
  exit 1
fi

echo "Resetting local state under $REPO_ROOT"

reset_dir() {
  local target="$1"
  local label="${target#$REPO_ROOT/}"

  if [[ -d "$target" ]]; then
    echo " - clearing $label"
  else
    echo " - creating $label"
  fi

  rm -rf -- "$target"
  mkdir -p -- "$target"
}

reset_dir "$REPO_ROOT/artifacts"
reset_dir "$REPO_ROOT/metadata"

WORKSPACES_DIR="$REPO_ROOT/workspaces"
if [[ ! -d "$WORKSPACES_DIR" ]]; then
  echo " - creating workspaces"
  mkdir -p -- "$WORKSPACES_DIR"
fi

echo " - cleaning workspaces (preserving templates)"
shopt -s nullglob dotglob
for entry in "$WORKSPACES_DIR"/*; do
  base="$(basename -- "$entry")"
  if [[ "$base" == "templates" ]]; then
    continue
  fi
  echo "   removing workspaces/$base"
  rm -rf -- "$entry"
done
shopt -u nullglob dotglob

MEMORIES_DIR="$REPO_ROOT/rag/memories"
if [[ -d "$MEMORIES_DIR" ]]; then
  shopt -s nullglob
  mem_files=("$MEMORIES_DIR"/*.jsonl)
  if (( ${#mem_files[@]} > 0 )); then
    echo " - deleting rag/memories JSONL files"
    rm -f -- "${mem_files[@]}"
  else
    echo " - no rag/memories JSONL files to delete"
  fi
  shopt -u nullglob
else
  echo " - skipping rag/memories cleanup (directory missing)"
fi

echo "Local state reset complete."
