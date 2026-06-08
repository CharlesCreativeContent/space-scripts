# space-scripts

Scripts to help with spaces.

## ts_to_mp3.py

Converts a `.ts` (MPEG Transport Stream) file into multiple MP3 files split into 2-hour segments.

### Prerequisites

FFmpeg must be installed and available on your PATH.

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Usage

```bash
python ts_to_mp3.py <input.ts> [options]
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--segment-duration SECS` | `7200` | Segment length in seconds (7200 = 2 hours) |
| `--output-dir DIR` | same as input | Directory for output MP3 files |
| `--quality 0-9` | `2` | VBR quality (0=best ~245kbps, 9=worst; 2≈190kbps) |
| `--audio-bitrate BITRATE` | — | CBR bitrate e.g. `192k` (overrides `--quality`) |

### Examples

```bash
# Basic usage — outputs alongside the input file
python ts_to_mp3.py my_recording.ts

# Custom output directory
python ts_to_mp3.py my_recording.ts --output-dir ./mp3s

# 1-hour segments at 192kbps CBR
python ts_to_mp3.py my_recording.ts --segment-duration 3600 --audio-bitrate 192k

# Best quality VBR
python ts_to_mp3.py my_recording.ts --quality 0
```

### Output

Input `my_recording.ts` produces:

```
my_recording_part000.mp3
my_recording_part001.mp3
my_recording_part002.mp3
...
```

Each segment starts at timestamp 0:00 and is independently playable.
