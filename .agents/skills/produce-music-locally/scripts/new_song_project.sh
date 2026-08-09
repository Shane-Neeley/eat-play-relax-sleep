#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /ABSOLUTE/PROJECT/PATH" >&2
  exit 2
fi

project_path=$1
if [[ "$project_path" != /* ]]; then
  echo "Use an absolute project path." >&2
  exit 1
fi

if [[ -e "$project_path" ]]; then
  echo "Refusing to reuse existing path: $project_path" >&2
  exit 1
fi

mkdir -p "$project_path"/{audio,beats,mixes,exports,notes}
touch "$project_path/notes/sources.txt"
printf '%s\n' "$project_path"
