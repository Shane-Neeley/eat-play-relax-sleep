#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 INPUT_VIDEO OUTPUT_WAV" >&2
  exit 2
fi

input_path=$1
output_path=$2

if [[ ! -f "$input_path" ]]; then
  echo "Input file not found: $input_path" >&2
  exit 1
fi

if [[ -e "$output_path" ]]; then
  echo "Refusing to overwrite existing output: $output_path" >&2
  exit 1
fi

ffmpeg_bin=$(command -v ffmpeg || true)
ffprobe_bin=$(command -v ffprobe || true)
if [[ -z "$ffmpeg_bin" || -z "$ffprobe_bin" ]]; then
  echo "FFmpeg and ffprobe are required." >&2
  exit 1
fi

if ! "$ffprobe_bin" -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$input_path" | grep -q .; then
  echo "No audio stream found in: $input_path" >&2
  exit 1
fi

output_dir=$(dirname "$output_path")
mkdir -p "$output_dir"

"$ffmpeg_bin" -hide_banner -loglevel error -i "$input_path" \
  -map 0:a:0 -vn -c:a pcm_f32le "$output_path"

"$ffprobe_bin" -v error \
  -show_entries format=filename,duration,size:stream=codec_name,sample_rate,channels \
  -of default=noprint_wrappers=1 "$output_path"
