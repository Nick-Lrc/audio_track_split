# Audio Track Split

---

## Description

- This script splits audio tracks with a CUE sheet

## Prerequisites

- [FFmpeg](https://ffmpeg.org/download.html)

## Usage

```text
Split audio tracks

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        input CUE sheet
  -o OUTPUT, --output OUTPUT
                        output directory
  --audio-encoding AUDIO_ENCODING
                        output audio encoding
  --text-encoding TEXT_ENCODING
                        text encoding
```

- Examples:
  - Standard split

  ```bash
  python track_split.py -i path/to/input/audio -o path/to/output/directory
  ```

  - Specify the encoding of the CUE sheet

  ```bash
  python track_split.py -i path/to/input/audio -o path/to/output/directory --text-encoding='utf-8'
  ```

  - Specify the encoding of the output audio files

  ```bash
  python track_split.py -i path/to/input/audio -o path/to/output/directory --audio-encoding='mp3'
  ```

---
