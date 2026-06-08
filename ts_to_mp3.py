#!/usr/bin/env python3
"""Convert a .ts (MPEG Transport Stream) file into 2-hour MP3 segments."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg not found on PATH.", file=sys.stderr)
        print("Install it with:", file=sys.stderr)
        print("  Ubuntu/Debian:  sudo apt install ffmpeg", file=sys.stderr)
        print("  macOS:          brew install ffmpeg", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a .ts transport stream to MP3 segments.",
        epilog="Example: ts_to_mp3.py recording.ts --output-dir ./output",
    )
    parser.add_argument("input_file", help="Path to the .ts input file")
    parser.add_argument(
        "--segment-duration",
        type=int,
        default=7200,
        metavar="SECS",
        help="Segment length in seconds (default: 7200 = 2 hours)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: same directory as input file)",
    )

    quality_group = parser.add_mutually_exclusive_group()
    quality_group.add_argument(
        "--quality",
        type=int,
        default=2,
        choices=range(10),
        metavar="0-9",
        help="VBR quality: 0=best (~245kbps), 9=worst (default: 2, ~190kbps)",
    )
    quality_group.add_argument(
        "--audio-bitrate",
        metavar="BITRATE",
        help="CBR bitrate, e.g. 192k (overrides --quality)",
    )
    return parser


def validate_input(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    if path.suffix.lower() != ".ts":
        raise ValueError(f"Expected a .ts file, got: {path.suffix}")
    if path.stat().st_size == 0:
        raise ValueError(f"File is empty: {path}")


def convert(
    input_path: Path,
    output_dir: Path,
    segment_duration: int,
    quality_args: list[str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = output_dir / f"{input_path.stem}_part%03d.mp3"

    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        *quality_args,
        "-f", "segment",
        "-segment_time", str(segment_duration),
        "-reset_timestamps", "1",
        str(output_pattern),
    ]

    print(f"Input:   {input_path}")
    print(f"Output:  {output_dir / (input_path.stem + '_part*.mp3')}")
    print(f"Segment: {segment_duration}s ({segment_duration // 3600}h {(segment_duration % 3600) // 60}m)")
    print()

    try:
        result = subprocess.run(cmd, capture_output=False)
    except KeyboardInterrupt:
        print("\nInterrupted — cleaning up partial files...", file=sys.stderr)
        _cleanup_partial_files(output_dir, input_path.stem)
        sys.exit(130)

    if result.returncode != 0:
        print("\nffmpeg failed — cleaning up partial files...", file=sys.stderr)
        _cleanup_partial_files(output_dir, input_path.stem)
        sys.exit(3)

    segments = sorted(output_dir.glob(f"{input_path.stem}_part*.mp3"))
    print(f"\nDone. Created {len(segments)} segment(s):")
    for seg in segments:
        size_mb = seg.stat().st_size / (1024 * 1024)
        print(f"  {seg.name}  ({size_mb:.1f} MB)")


def _cleanup_partial_files(output_dir: Path, stem: str) -> None:
    for f in output_dir.glob(f"{stem}_part*.mp3"):
        try:
            f.unlink()
        except OSError:
            pass


def main() -> None:
    check_ffmpeg()

    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input_file)

    try:
        validate_input(input_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    output_dir = args.output_dir if args.output_dir is not None else input_path.parent

    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True)
        except OSError as exc:
            print(f"Error: cannot create output directory: {exc}", file=sys.stderr)
            sys.exit(2)

    if not output_dir.is_dir():
        print(f"Error: output path is not a directory: {output_dir}", file=sys.stderr)
        sys.exit(2)

    if args.audio_bitrate:
        quality_args = ["-b:a", args.audio_bitrate]
    else:
        quality_args = ["-q:a", str(args.quality)]

    convert(input_path, output_dir, args.segment_duration, quality_args)


if __name__ == "__main__":
    main()
