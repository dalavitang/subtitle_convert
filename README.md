# TCSync

Subtitle timecode conversion and alignment tool. Converts between Avid Subcap, CSV, PR, SRT, and Markdown subtitle formats.

Key features:

- **Five subtitle formats** — Read and write Avid Subcap (`.txt`), CSV (`.csv`), PR dot-timecode (`.txt`), SRT (`.srt`), and Markdown tables (`.md`).
- **Timecode alignment** — Shift all timecodes by a frame offset. Specify origin and target timecodes; the script computes the difference and realigns every caption.
- **Combine/merge mode** — Feed two subtitle files at once, aligned. Overlapping blocks are merged by tolerance, and the result is written as one unified file.
- **Multi-language splitting** — If your subtitle file contains multiple language columns, split them into independent files (`_L1`, `_L2`, etc.).
- **Auto framerate detection** — For SRT input, the script scans millisecond values and matches the best common framerate (24, 25, 30, 48, 50, 60 fps). Override with `-r` if needed.
- **Drop-frame support** — Timecode in `HH:MM:SS;FF` format for 29.97 and 59.94 fps workflows.
- **Configurable CSV quoting** — Detect or override the CSV quote character (`\` or `"`) for both reading and writing.
- **Multiple output formats** — Specify `-of` more than once to produce several output files from a single input.

## Usage

```
python subtitle_convert.py [<input_file> [<output_file>]] [OPTIONS]
```

### Arguments

Positional arguments (`input_file`, `output_file`) are optional when the equivalent flags are used.

| Flag | Description |
|------|-------------|
| `-i`, `--input` | Input file. Repeatable — specify twice for combine mode. |
| `-o`, `--output` | Output file path. Required for combine mode. |

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-if`, `--inputformat` | *(auto)* | Input format. Required for `.txt` files. Choices: `avid`, `csv`, `pr`, `srt`, `md`. Otherwise auto-detected from file extension. |
| `-of`, `--outputformat` | *(auto)* | Output format. Repeatable. Choices: `avid`, `csv`, `pr`, `srt`, `md`. Auto-detected from `-o` extension if omitted. |
| `-m`, `--splitmulti N` | *(off)* | Split into N single-language files. Language columns beyond N are joined into the last file. |
| `-r`, `--framerate F` | auto / 25 | Override framerate. Auto-detected for SRT input; defaults to 25 for other formats. |
| `-f`, `--fromtimecode TC` | `00:00:00:00` | Origin timecode for alignment (format: `HH:MM:SS:FF`). |
| `-t`, `--totimecode TC` | `00:00:00:00` | Target timecode for alignment. When different from `-f`, the offset is applied to all captions. |
| `-df`, `--dropframe` | *(auto)* | Force drop-frame timecode. If omitted and framerate is 29.97 or 59.94, prompts interactively. |
| `-tl`, `--tolerance N` | `0` | Frame tolerance when merging overlapping blocks in combine mode. |
| `-D`, `--decoder ENC` | `utf-8-sig` | Input file encoding. |
| `-qr`, `--quoteread CHAR` | auto | CSV quote character for reading. Use bare `-qr` to prompt interactively. |
| `-qw`, `--quotewrite CHAR` | auto | CSV quote character for writing. Use bare `-qw` to prompt interactively. |

### Timecode format

All non-SRT formats use `HH:MM:SS:FF` (non-drop-frame) or `HH:MM:SS;FF` (drop-frame). SRT uses `HH:MM:SS,mmm` timestamps, which are converted to frame-based timecode internally based on the framerate.

### Examples

The simplest invocation — input and output formats are auto-detected from file extensions:
```
python subtitle_convert.py subtitle_01.srt subtitle_01.csv
```

Convert SRT to Avid Subcap format:
```
python subtitle_convert.py subs.srt -of avid -o output.txt
```

Shift timecodes by 1 hour, output to SRT:
```
python subtitle_convert.py input.srt -f 00:00:00:00 -t 01:00:00:00 -o aligned.srt
```

Combine two SRT files, merge overlapping blocks with 5-frame tolerance:
```
python subtitle_convert.py -i dialog.srt -i titles.srt -o combined.srt -tl 5
```

Split a multi-language CSV into 3 separate SRT files:
```
python subtitle_convert.py multilang.csv -m 3 -of srt -o output.srt
```

Convert Markdown table to CSV:
```
python subtitle_convert.py table.md -of csv -o output.csv
```

Convert a `.txt` file in PR format to SRT at 24 fps:
```
python subtitle_convert.py input.txt -if pr -r 24 -o output.srt
```

Produce Avid and Markdown output from one input:
```
python subtitle_convert.py subs.srt -of avid -of md -o output
```

Override CSV quote character for reading and writing:
```
python subtitle_convert.py subs.csv -qr -qw -o output.srt
```

### Format notes

- **Markdown (`.md`)** — Roundtrip subtitles through LLMs for translation, proofreading, or quality checks. The pipe-delimited table format is easy for language models to parse and generate.
- **CSV (`.csv`)** — Export subtitles into a table format for review, editing, or sharing with non-technical collaborators who can open the file in a spreadsheet application.
- **SRT (`.srt`)** — The most widely supported subtitle format. Use as an interchange when moving subtitles between different tools or platforms.
- **Avid Subcap (`.txt`)** — Native caption format for Avid Media Composer. Requires `-if avid`.
- **PR (`.txt`)** — Native subtitle format for Adobe Premiere Pro. Requires `-if pr`.

## Requirements

- Python 3.7 or later

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE](LICENSE.txt) for the full license text.
