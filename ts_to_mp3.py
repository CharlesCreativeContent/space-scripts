#!/usr/bin/env python3
"""Convert a .ts (MPEG Transport Stream) file into 2-hour MP3 segments."""

import argparse
import math
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


def probe_duration(input_path: Path) -> float | None:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            return float(result.stdout.strip())
        except ValueError:
            pass
    return None


_VBR_KBPS = {0: 245, 1: 225, 2: 190, 3: 175, 4: 165, 5: 130, 6: 115, 7: 100, 8: 85, 9: 65}


def _parse_bitrate_bps(bitrate_str: str) -> int:
    s = bitrate_str.strip().lower()
    if s.endswith("k"):
        return int(float(s[:-1]) * 1000)
    if s.endswith("m"):
        return int(float(s[:-1]) * 1_000_000)
    return int(s)


def _estimate_output_bytes(duration_secs: float, quality_args: list[str]) -> int:
    if "-b:a" in quality_args:
        bitrate_bps = _parse_bitrate_bps(quality_args[quality_args.index("-b:a") + 1])
    else:
        quality = int(quality_args[quality_args.index("-q:a") + 1])
        bitrate_bps = _VBR_KBPS.get(quality, 190) * 1000
    return int(duration_secs * bitrate_bps / 8 * 1.1)  # 10% headroom


def check_disk_space(output_dir: Path, duration_secs: float, quality_args: list[str]) -> None:
    needed = _estimate_output_bytes(duration_secs, quality_args)
    free = shutil.disk_usage(output_dir).free
    if needed > free:
        needed_mb = needed / (1024 * 1024)
        free_mb = free / (1024 * 1024)
        raise ValueError(
            f"Insufficient disk space: need ~{needed_mb:.0f} MB, only {free_mb:.0f} MB free"
        )


def _fmt_duration(secs: float) -> str:
    h = int(secs) // 3600
    m = (int(secs) % 3600) // 60
    s = int(secs) % 60
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def convert(
    input_path: Path,
    output_dir: Path,
    segment_duration: int,
    quality_args: list[str],
    duration: float | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = output_dir / f"{input_path.stem}_part%03d.mp3"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        *quality_args,
        "-f", "segment",
        "-segment_time", str(segment_duration),
        "-reset_timestamps", "1",
        str(output_pattern),
    ]

    print(f"Input:    {input_path}", end="")
    if duration is not None:
        n_segments = math.ceil(duration / segment_duration)
        est_mb = _estimate_output_bytes(duration, quality_args) / (1024 * 1024)
        print(f"  ({_fmt_duration(duration)})")
        print(f"Output:   {output_dir / (input_path.stem + '_part*.mp3')}")
        print(f"Segments: {n_segments} × {_fmt_duration(segment_duration)}")
        print(f"Est. size: ~{est_mb:.0f} MB total")
    else:
        print()
        print(f"Output:   {output_dir / (input_path.stem + '_part*.mp3')}")
        print(f"Segment:  {_fmt_duration(segment_duration)}")
    print()

    try:
        result = subprocess.run(cmd, capture_output=False)
    except KeyboardInterrupt:
        print("\nInterrupted — removing partial segment, keeping completed ones...", file=sys.stderr)
        _cleanup_last_segment(output_dir, input_path.stem)
        sys.exit(130)

    if result.returncode != 0:
        print("\nffmpeg failed — removing partial segment, keeping completed ones...", file=sys.stderr)
        _cleanup_last_segment(output_dir, input_path.stem)
        sys.exit(3)

    segments = sorted(output_dir.glob(f"{input_path.stem}_part*.mp3"))
    print(f"\nDone. Created {len(segments)} segment(s):")
    for seg in segments:
        size_mb = seg.stat().st_size / (1024 * 1024)
        print(f"  {seg.name}  ({size_mb:.1f} MB)")


def _cleanup_last_segment(output_dir: Path, stem: str) -> None:
    """Remove only the last (potentially partial) segment; keep completed ones."""
    files = sorted(output_dir.glob(f"{stem}_part*.mp3"))
    if not files:
        return
    partial = files[-1]
    try:
        partial.unlink()
        print(f"  Removed partial: {partial.name}", file=sys.stderr)
    except OSError:
        pass
    if len(files) > 1:
        print(f"  Kept {len(files) - 1} completed segment(s) in {output_dir}", file=sys.stderr)


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

    duration = probe_duration(input_path)

    if duration is not None:
        try:
            check_disk_space(output_dir, duration, quality_args)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

    convert(input_path, output_dir, args.segment_duration, quality_args, duration)


if __name__ == "__main__":
    main()
