#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="$PROJECT_ROOT/build/demos"
mkdir -p "$OUTPUT_ROOT"
for beat in "$PROJECT_ROOT"/examples/beats/*.beat; do
  name="$(basename "$beat" .beat)"
  "$PROJECT_ROOT/scripts/eprs" render "$beat" --out "$OUTPUT_ROOT/$name.wav"
  "$PROJECT_ROOT/scripts/eprs" visualize "$beat" --out "$OUTPUT_ROOT/$name.svg"
done
