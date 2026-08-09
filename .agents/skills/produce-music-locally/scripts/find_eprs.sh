#!/usr/bin/env bash
set -euo pipefail

start_path=${1:-$PWD}
if [[ -f "$start_path" ]]; then
  start_path=$(dirname "$start_path")
fi

find_root() {
  local candidate=$1
  candidate=$(cd "$candidate" 2>/dev/null && pwd) || return 1
  while [[ "$candidate" != / ]]; do
    if [[ -x "$candidate/scripts/eprs" && -f "$candidate/pyproject.toml" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    candidate=$(dirname "$candidate")
  done
  return 1
}

if find_root "$start_path"; then
  exit 0
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if find_root "$script_dir/../../../.."; then
  exit 0
fi

echo "EPRS repository not found from: $start_path" >&2
exit 1
