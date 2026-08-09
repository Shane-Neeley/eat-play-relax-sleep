#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 AUDIO_FILE" >&2
  exit 2
fi

audio_path=$1
if [[ ! -f "$audio_path" ]]; then
  echo "Audio file not found: $audio_path" >&2
  exit 1
fi

ffmpeg_bin=$(command -v ffmpeg || true)
ffprobe_bin=$(command -v ffprobe || true)
if [[ -z "$ffmpeg_bin" || -z "$ffprobe_bin" ]]; then
  echo "FFmpeg and ffprobe are required." >&2
  exit 1
fi

echo "File properties"
"$ffprobe_bin" -v error \
  -show_entries format=filename,duration,size:stream=codec_name,sample_rate,channels \
  -of default=noprint_wrappers=1 "$audio_path"

echo "Levels"
"$ffmpeg_bin" -hide_banner -nostats -i "$audio_path" -af volumedetect -f null - 2>&1 \
  | awk '/mean_volume:|max_volume:/'
