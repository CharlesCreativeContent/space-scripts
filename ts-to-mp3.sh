#!/usr/bin/env bash
set -euo pipefail

SEGMENT_SECS=7200  # 2 hours

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] <input.ts>

Convert a MPEG Transport Stream (.ts) file into 2-hour MP3 segments.

Options:
  -d <dir>      Output directory (default: same directory as input file)
  -s <seconds>  Segment length in seconds (default: 7200 = 2 hours)
  -h            Show this help message

Output files are named <basename>_part_001.mp3, <basename>_part_002.mp3, ...

Examples:
  $(basename "$0") recording.ts
  $(basename "$0") -d /tmp/output -s 3600 recording.ts
EOF
}

out_dir=""
segment_secs=$SEGMENT_SECS

while getopts ":d:s:h" opt; do
  case $opt in
    d) out_dir="$OPTARG" ;;
    s) segment_secs="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Error: option -$OPTARG requires an argument." >&2; usage >&2; exit 1 ;;
    \?) echo "Error: unknown option -$OPTARG." >&2; usage >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -lt 1 ]]; then
  echo "Error: no input file specified." >&2
  usage >&2
  exit 1
fi

input="$1"

if ! command -v ffmpeg &>/dev/null; then
  echo "Error: ffmpeg is not installed or not in PATH." >&2
  echo "Install it with: brew install ffmpeg  (macOS) or  sudo apt install ffmpeg  (Debian/Ubuntu)" >&2
  exit 1
fi

if [[ ! -f "$input" ]]; then
  echo "Error: file not found: $input" >&2
  exit 1
fi

if [[ ! -r "$input" ]]; then
  echo "Error: file is not readable: $input" >&2
  exit 1
fi

if ! [[ "$segment_secs" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: segment length must be a positive integer (got: $segment_secs)" >&2
  exit 1
fi

basename="${input##*/}"
basename="${basename%.*}"

if [[ -z "$out_dir" ]]; then
  out_dir="$(dirname "$input")"
fi

mkdir -p "$out_dir"

echo "Input:          $input"
echo "Output dir:     $out_dir"
echo "Segment length: ${segment_secs}s ($(( segment_secs / 3600 ))h $(( (segment_secs % 3600) / 60 ))m)"
echo ""

ffmpeg -i "$input" \
  -vn \
  -f segment \
  -segment_time "$segment_secs" \
  -c:a libmp3lame \
  -q:a 2 \
  "${out_dir}/${basename}_part_%03d.mp3"

echo ""
echo "Done. Segments written to: $out_dir"
