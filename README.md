# Subtitle Convert

Subtitle timecode conversion and alignment tool. Converts between Avid Subcap, CSV, PR, SRT, and Markdown subtitle formats.

Key features:

- **Five subtitle formats** — Read and write Avid Subcap (`.txt`), CSV (`.csv`), Adobe Premiere Pro native subtitles (`.txt`), SRT (`.srt`), and Markdown tables (`.md`).
- **Timecode alignment** — Shift all timecodes by a frame offset. Specify origin and target timecodes; the script computes the difference and realigns every caption.
- **Combine/merge mode** — Feed two subtitle files at once, aligned. Overlapping blocks are merged by tolerance, and the result is written as one unified file.
- **Multi-language splitting** — If your subtitle file contains multiple language columns, split them into independent files (`_L1`, `_L2`, etc.).
- **Auto framerate detection** — For SRT input, the script scans millisecond values and matches the best common framerate (24, 25, 30, 48, 50, 60 fps). Override with `-r` if needed.
- **Drop-frame support** — Timecode in `HH:MM:SS;FF` format for 29.97 and 59.94 fps workflows.
- **Configurable CSV quoting** — Detect or override the CSV quote character (`\` or `"`) for both reading and writing.
- **Multiple output formats** — Specify `-of` more than once to produce several output files from a single input.
- **Timestamp passthrough** — Use `-c` to preserve raw SRT timestamps through CSV/MD roundtrips without converting to frame-based timecode.

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
| `-if`, `--inputformat` | *(auto)* | Input format. Required for `.txt` files (disambiguate Avid Subcap vs PR). Optional for `.csv`, `.srt`, `.md` — auto-detected from extension. Choices: `avid`, `csv`, `pr`, `srt`, `md`. |
| `-of`, `--outputformat` | *(auto)* | Output format. Required for `.txt` output or when `-o` has no extension. Optional otherwise — auto-detected from `-o` extension. Repeatable to produce multiple outputs. Choices: `avid`, `csv`, `pr`, `srt`, `md`. |
| `-m`, `--splitmulti N` | *(off)* | Split into N single-language files. Language columns beyond N are joined into the last file. |
| `-r`, `--framerate F` | auto / 25 | Override framerate. Auto-detected for SRT input; defaults to 25 for other formats. |
| `-f`, `--fromtimecode TC` | `00:00:00:00` | Origin timecode for alignment (format: `HH:MM:SS:FF`). |
| `-t`, `--totimecode TC` | `00:00:00:00` | Target timecode for alignment. When different from `-f`, the offset is applied to all captions. |
| `-df`, `--dropframe` | *(auto)* | Force drop-frame timecode. If omitted and framerate is 29.97 or 59.94, prompts interactively. |
| `-tl`, `--tolerance N` | `0` | Frame tolerance when merging overlapping blocks in combine mode. |
| `-c`, `--copytimestamp` | *(off)* | Skip timestamp ↔ timecode conversion when reading/writing SRT. Preserves raw `HH:MM:SS,mmm` strings in CSV/MD roundtrips. Incompatible with alignment. |
| `-D`, `--decoder ENC` | `utf-8-sig` | Input file encoding. |
| `-qr`, `--quoteread CHAR` | auto | CSV quote character for reading. Use bare `-qr` to prompt interactively. |
| `-qw`, `--quotewrite CHAR` | auto | CSV quote character for writing. Use bare `-qw` to prompt interactively. |

### Option details

**`-if` / `--inputformat`**

For `.csv`, `.srt`, and `.md` files the format is determined entirely by the file extension. `-if` has no effect — passing `-if srt` with a `.csv` file will still treat it as CSV.

For `.txt` files `-if` is **required**. Avid Subcap and PR both use the `.txt` extension and cannot be distinguished automatically.

**`-of` / `--outputformat`**

If `-o` specifies a known extension (`.csv`, `.srt`, `.md`), the output format is auto-detected and `-of` is optional. For `.txt` output or output files with no extension, `-of` is required. Specify `-of` multiple times to write the same data in several formats from one run.

**`-r` / `--framerate`**

For SRT input the framerate is auto-detected from millisecond values in timestamps. Use `-r` to override. For all other input formats the default is 25 fps. The framerate affects timecode-to-timestamp conversion and timecode alignment math.

**`-f` / `--fromtimecode` and `-t` / `--totimecode`**

Set both to apply a timecode shift. The script computes the frame difference `totimecode − fromtimecode` and offsets every caption. Use `HH:MM:SS:FF` format. When the two values are equal no alignment is performed.

**`-df` / `--dropframe`**

Enables drop-frame timecode (`HH:MM:SS;FF`). If omitted and the framerate is 29.97 or 59.94 (common drop-frame rates), the script prompts interactively. For all other framerates drop-frame is off by default.

**`-m` / `--splitmulti`**

Splits multi-language data into N separate output files (`_L1`, `_L2`, …, `_LN`). If the data has more language columns than N, the excess columns are joined into the last file. If fewer, empty lines are padded. Use with `-of` to control the output format of the split files.

**`-tl` / `--tolerance`**

In combine mode (two input files), this is the number of frames by which overlapping blocks may differ before they are considered separate entries. Larger values merge more aggressively.

**`-c` / `--copytimestamp`**

Skips the `HH:MM:SS,mmm` (SRT timestamp) ↔ `HH:MM:SS:FF` (timecode) conversion normally performed when reading or writing SRT files. With `-c`, timestamp strings pass through as-is. Useful for round-tripping subtitles through CSV or Markdown without losing the original SRT millisecond values.

Format-specific behavior:

- **SRT input/output with `-c`**: raw timestamps are stored and written directly. No framerate needed. `-r` is ignored (a warning is shown).
- **CSV/MD input with `-c`**: if the file contains timestamps, they are preserved as-is. If it contains timecodes, no conversion happens.
- **Avid/PR with `-c`**: the user is prompted — `-c` has no effect on these formats since they always use timecode. CSV/MD input containing timestamps destined for avid/pr output is converted to timecode regardless of `-c`.
- **Drop-frame timelines**: when SRT files originate from a drop-frame timeline (29.97 or 59.94 fps), use `-c` to avoid precision loss. The frame-to-millisecond math in drop-frame timecode is inherently lossy — converting through timecode and back can shift timestamps by a frame. `-c` preserves the original SRT millisecond values intact.
- **Incompatibilities**: `-c` cannot be used with timecode alignment (`-f`/`-t`).

**`-qr` / `--quoteread` and `-qw` / `--quotewrite`**

For CSV files, these set the quote character used for reading and writing respectively. By default the script auto-detects the quote character from the first line of the input. Use bare `-qr` or `-qw` (without a value) to be prompted interactively.

**`-D` / `--decoder`**

File encoding for both input and output. Defaults to `utf-8-sig` (UTF-8 with BOM handling).

### Output file naming

The output file name is constructed from the base name and an extension per output format.

**Base name:**

| Condition | Base name |
|-----------|-----------|
| `-o` specified | Stem of `-o` (extension stripped) |
| No `-o` | Stem of the input file |

If timecode alignment is active (`-f` and `-t` differ), a suffix is appended:

```
{base}_alignedTo_HH-MM-SS-FF_{fps}FPS
```

When the base name already contains `_alignedTo_` from a previous alignment, the old suffix is replaced rather than stacked.

**Extension per format:**

| Format | Extension |
|--------|-----------|
| `avid` | `.txt` |
| `csv` | `.csv` |
| `pr` | `.txt` |
| `srt` | `.srt` |
| `md` | `.md` |

**Resulting filenames:**

| Mode | Pattern |
|------|---------|
| Single `-of` (or auto-detected) | `{base}{ext}` |
| Multiple `-of` | `{base}{ext1}`, `{base}{ext2}`, … |
| Split mode (`-m N`) | `{base}_L1{ext}`, `{base}_L2{ext}`, …, `{base}_LN{ext}` |
| Split + multiple `-of` | `{base}_L1{ext1}`, `{base}_L1{ext2}`, …, `{base}_LN{ext1}`, `{base}_LN{ext2}` |

**When `-o` has an extension that conflicts with `-of`:** the extension from `-of` wins. The base name is always derived from `-o` (stem only), and each output format appends its own extension. For example, `-o out.csv -of srt -of md` produces `out.srt` and `out.md` — the `.csv` in `-o` is discarded.

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

Preserve SRT timestamps when converting to CSV:
```
python subtitle_convert.py subs.srt output.csv -c
```

Roundtrip through Markdown without losing millisecond precision:
```
python subtitle_convert.py subs.srt table.md -c
python subtitle_convert.py table.md subs.srt -c
```

### Format notes

- **Markdown (`.md`)** — Roundtrip subtitles through LLMs for translation, proofreading, or quality checks. The pipe-delimited table format is easy for language models to parse and generate.
- **CSV (`.csv`)** — Export subtitles into a table format for review, editing, or sharing with non-technical collaborators who can open the file in a spreadsheet application.
- **SRT (`.srt`)** — The most widely supported subtitle format. Use as an interchange when moving subtitles between different tools or platforms.
- **Avid Subcap (`.txt`)** — Native caption format for Avid Media Composer. Requires `-if avid`.
- **PR (`.txt`)** — Native subtitle format for Adobe Premiere Pro. Requires `-if pr`.

## Requirements

- Python 3.7 or later

---

**Note:** Portions of this codebase were generated by an LLM (large language model). While the script implements the described functionality, it should be reviewed carefully before use in production subtitle workflows. Always verify the output against your source material.

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE](LICENSE.txt) for the full license text.
