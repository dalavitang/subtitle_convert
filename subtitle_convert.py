import argparse
import sys
import os
import re
import csv
import io
from dataclasses import dataclass

CSV_QUOTE_IN = '\\'
CSV_QUOTE_OUT = '\\'


@dataclass
class CaptionBlock:
    timecode_in: str
    timecode_out: str
    lines: list
    frame_in: int = 0
    frame_out: int = 0


def timecode_to_frames(tc_string, framerate, drop_frame=False):
    tc_string = tc_string.strip()
    tc_hh, tc_mm, tc_ss, tc_ff = (
        int(tc_string[0:2]),
        int(tc_string[3:5]),
        int(tc_string[6:8]),
        int(tc_string[9:11]),
    )
    time_base = round(framerate)
    if not drop_frame:
        frame_number = tc_ff + (((tc_hh * 60 + tc_mm) * 60) + tc_ss) * time_base
    else:
        total_minutes = tc_hh * 60 + tc_mm
        frames_dropped = round(framerate * 2 / 30)
        frame_number = (
            (total_minutes * 60 + tc_ss) * time_base
            + tc_ff
            - (frames_dropped * (total_minutes - total_minutes // 10))
        )
    return frame_number


def frames_to_timecode(frame_number, framerate, drop_frame=False):
    time_base = round(framerate)
    if not drop_frame:
        tc_ff = int(frame_number % time_base)
        total_seconds = frame_number // time_base
        tc_hh = int(total_seconds // 3600)
        tc_mm = int((total_seconds - tc_hh * 3600) // 60)
        tc_ss = int(total_seconds % 60)
        tc_string = (
            str(tc_hh).zfill(2)
            + ":"
            + str(tc_mm).zfill(2)
            + ":"
            + str(tc_ss).zfill(2)
            + ":"
            + str(tc_ff).zfill(2)
        )
    else:
        frames_dropped = round(framerate * 2 / 30)
        frames_ten_minutes = round(framerate * 600)
        frames_per_minute = round(framerate) * 60 - frames_dropped
        d = frame_number // frames_ten_minutes
        m = frame_number % frames_ten_minutes
        if m > frames_dropped:
            frame_number = (
                frame_number
                + frames_dropped * 9 * d
                + frames_dropped * ((m - frames_dropped) // frames_per_minute)
            )
        else:
            frame_number = frame_number + frames_dropped * 9 * d
        tc_hh = ((frame_number // time_base) // 60) // 60
        tc_mm = ((frame_number // time_base) // 60) % 60
        tc_ss = (frame_number // time_base) % 60
        tc_ff = frame_number % time_base
        tc_string = (
            str(tc_hh).zfill(2)
            + ":"
            + str(tc_mm).zfill(2)
            + ":"
            + str(tc_ss).zfill(2)
            + ";"
            + str(tc_ff).zfill(2)
        )
    return tc_string


def timecode_to_timestamp(tc_string, framerate):
    frame_time = 1000 / framerate
    tc_hh, tc_mm, tc_ss, tc_ff = (
        int(tc_string[0:2]),
        int(tc_string[3:5]),
        int(tc_string[6:8]),
        int(tc_string[9:11]),
    )
    ts_ms = str(int(int(tc_ff) * frame_time)).zfill(3)
    timestamp = (
        str(tc_hh).zfill(2)
        + ":"
        + str(tc_mm).zfill(2)
        + ":"
        + str(tc_ss).zfill(2)
        + ","
        + ts_ms
    )
    return timestamp


def timestamp_to_timecode(timestamp, framerate):
    frame_time = 1000 / framerate
    tc_hh, tc_mm, ts_ss_ms = timestamp.split(":")
    tc_ss, ts_ms = ts_ss_ms.split(",")
    tc_ff = round(int(ts_ms) / frame_time)
    tc_string = tc_hh + ":" + tc_mm + ":" + tc_ss + ":" + str(tc_ff).zfill(2)
    return tc_string


def align_timecode(source_tc, frames_diff, framerate, drop_frame=False):
    target_frame_count = (
        timecode_to_frames(source_tc, framerate, drop_frame) + frames_diff
    )
    return frames_to_timecode(target_frame_count, framerate, drop_frame)


def _md_escape_field(text):
    return text.replace("|", "\\|").replace("\n", "<br>")


def _md_table_row(fields):
    return "| " + " | ".join(_md_escape_field(str(f)) for f in fields) + " |\n"


def _csv_write_row(fields, quotechar):
    buf = io.StringIO()
    csv.writer(
        buf, quotechar=quotechar, quoting=csv.QUOTE_ALL, lineterminator="\n"
    ).writerow(fields)
    return buf.getvalue()


def align_blocks(blocks, offset_frames, framerate, drop_frame):
    for b in blocks:
        b.timecode_in = align_timecode(b.timecode_in, offset_frames, framerate, drop_frame)
        b.timecode_out = align_timecode(b.timecode_out, offset_frames, framerate, drop_frame)
    return blocks


def split_blocks(blocks, language_index, target_count):
    result = []
    for b in blocks:
        if language_index < target_count - 1:
            line = b.lines[language_index] if language_index < len(b.lines) else ""
            result.append(CaptionBlock(b.timecode_in, b.timecode_out, [line]))
        else:
            overflow = b.lines[language_index:] if language_index < len(b.lines) else [""]
            result.append(CaptionBlock(b.timecode_in, b.timecode_out, overflow))
    return result


def pad_blocks(blocks, target_count):
    for b in blocks:
        while len(b.lines) < target_count:
            b.lines.append("")
    return blocks


def set_frame_numbers(blocks, framerate, drop_frame):
    for b in blocks:
        b.frame_in = timecode_to_frames(b.timecode_in, framerate, drop_frame)
        b.frame_out = timecode_to_frames(b.timecode_out, framerate, drop_frame)


def merge_blocks(blocks1, blocks2, framerate, drop_frame, tolerance=0):
    result = []
    overlap_messages = []
    i = j = 0

    while i < len(blocks1) and j < len(blocks2):
        b1 = blocks1[i]
        b2 = blocks2[j]
        diff_in = abs(b1.frame_in - b2.frame_in)

        if diff_in <= tolerance:
            common_in = min(b1.frame_in, b2.frame_in)
            tc_in = b1.timecode_in if b1.frame_in <= b2.frame_in else b2.timecode_in

            diff_out = abs(b1.frame_out - b2.frame_out)
            if diff_out <= tolerance:
                common_out = min(b1.frame_out, b2.frame_out)
                tc_out = b1.timecode_out if b1.frame_out <= b2.frame_out else b2.timecode_out
                result.append(CaptionBlock(tc_in, tc_out,
                                           b1.lines + b2.lines,
                                           common_in, common_out))
                i += 1
                j += 1
            elif b1.frame_out > b2.frame_out:
                k = j + 1
                while k < len(blocks2) and blocks2[k].frame_out + tolerance < b1.frame_out:
                    k += 1
                if k < len(blocks2):
                    for m in range(j, k + 1):
                        fm_in = max(b1.frame_in, blocks2[m].frame_in)
                        fm_out = blocks2[m].frame_out if m < k else min(b1.frame_out, blocks2[k].frame_out)
                        tc_in_split = blocks2[m].timecode_in if fm_in == blocks2[m].frame_in else b1.timecode_in
                        tc_out_split = blocks2[m].timecode_out if m < k else b1.timecode_out
                        result.append(CaptionBlock(tc_in_split, tc_out_split,
                                                   b1.lines + blocks2[m].lines,
                                                   fm_in, fm_out))
                    i += 1
                    j = k + 1
                else:
                    result.append(CaptionBlock(tc_in, b1.timecode_out,
                                               b1.lines + b2.lines,
                                               common_in, b1.frame_out))
                    overlap_messages.append(
                        f"\033[33mOverlap: {b1.timecode_in}-{b1.timecode_out} and "
                        f"{b2.timecode_in}-{b2.timecode_out} (merged at start, durations differ)\033[0m"
                    )
                    i += 1
                    j += 1
            else:
                k = i + 1
                while k < len(blocks1) and blocks1[k].frame_out + tolerance < b2.frame_out:
                    k += 1
                if k < len(blocks1):
                    for m in range(i, k + 1):
                        fm_in = max(blocks1[m].frame_in, b2.frame_in)
                        fm_out = blocks1[m].frame_out if m < k else min(blocks1[m].frame_out, b2.frame_out)
                        tc_in_split = blocks1[m].timecode_in if fm_in == blocks1[m].frame_in else b2.timecode_in
                        tc_out_split = blocks1[m].timecode_out if m < k else b2.timecode_out
                        result.append(CaptionBlock(tc_in_split, tc_out_split,
                                                   blocks1[m].lines + b2.lines,
                                                   fm_in, fm_out))
                    i = k + 1
                    j += 1
                else:
                    common_out = min(b1.frame_out, b2.frame_out)
                    tc_out = b2.timecode_out if b2.frame_out <= b1.frame_out else b1.timecode_out
                    result.append(CaptionBlock(tc_in, tc_out,
                                               b1.lines + b2.lines,
                                               common_in, common_out))
                    overlap_messages.append(
                        f"\033[33mOverlap: {b1.timecode_in}-{b1.timecode_out} and "
                        f"{b2.timecode_in}-{b2.timecode_out} (merged at start, durations differ)\033[0m"
                    )
                    i += 1
                    j += 1
        elif b1.frame_in < b2.frame_in:
            if b1.frame_out > b2.frame_in:
                overlap_messages.append(
                    f"\033[33mOverlap: {b1.timecode_in}-{b1.timecode_out} and "
                    f"{b2.timecode_in}-{b2.timecode_out}\033[0m"
                )
            result.append(b1)
            i += 1
        else:
            if b2.frame_out > b1.frame_in:
                overlap_messages.append(
                    f"\033[33mOverlap: {b1.timecode_in}-{b1.timecode_out} and "
                    f"{b2.timecode_in}-{b2.timecode_out}\033[0m"
                )
            result.append(b2)
            j += 1

    if result and i < len(blocks1):
        last = result[-1]
        if last.frame_out > blocks1[i].frame_in:
            overlap_messages.append(
                f"\033[33mOverlap after merge: last block {last.timecode_in}-{last.timecode_out} "
                f"overlaps trailing {blocks1[i].timecode_in}-{blocks1[i].timecode_out}\033[0m"
            )
    if result and j < len(blocks2):
        last = result[-1]
        if last.frame_out > blocks2[j].frame_in:
            overlap_messages.append(
                f"\033[33mOverlap after merge: last block {last.timecode_in}-{last.timecode_out} "
                f"overlaps trailing {blocks2[j].timecode_in}-{blocks2[j].timecode_out}\033[0m"
            )

    result.extend(blocks1[i:])
    result.extend(blocks2[j:])
    return result, overlap_messages


def read_amc(lines):
    blocks = []
    i = 0
    tc_pattern = re.compile(r"^\d\d:\d\d:\d\d:\d\d \d\d:\d\d:\d\d:\d\d")
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "<begin subtitles>":
            i += 1
            continue
        if stripped == "<end subtitles>":
            break
        if tc_pattern.match(stripped):
            tc_in, tc_out = stripped.split()
            i += 1
            cap_lines = []
            while i < len(lines):
                cap = lines[i].strip()
                if not cap or cap == "<end subtitles>" or tc_pattern.match(cap):
                    break
                cap_lines.append(cap)
                i += 1
            blocks.append(CaptionBlock(tc_in, tc_out, cap_lines))
        else:
            i += 1
    return blocks


def read_csv(lines, quotechar):
    blocks = []
    reader = csv.reader(lines, quotechar=quotechar)
    for row in reader:
        if not row or len(row) < 2:
            continue
        blocks.append(CaptionBlock(row[0], row[1], row[2:] if len(row) > 2 else []))
    return blocks


def read_pr(lines):
    blocks = []
    tc_pattern = re.compile(r"^\d\d.\d\d.\d\d.\d\d - \d\d.\d\d.\d\d.\d\d")
    line_count = len(lines)
    tc_indices = [i for i in range(line_count) if tc_pattern.match(lines[i])]
    for idx, i in enumerate(tc_indices):
        tc_in, tc_out = lines[i].strip().split(" - ")
        end = tc_indices[idx + 1] if idx + 1 < len(tc_indices) else line_count
        cap_lines = []
        for j in range(i + 1, end):
            cap = lines[j].strip()
            if not cap:
                break
            cap_lines.append(cap)
        blocks.append(CaptionBlock(tc_in, tc_out, cap_lines))
    return blocks


def read_srt(lines, framerate):
    blocks = []
    tc_pattern = re.compile(r"^\d\d:\d\d:\d\d,\d\d\d --> \d\d:\d\d:\d\d,\d\d\d")
    line_count = len(lines)
    tc_indices = [i for i in range(line_count) if tc_pattern.match(lines[i])]
    for idx, i in enumerate(tc_indices):
        ts_in, ts_out = lines[i].strip().split(" --> ")
        tc_in = timestamp_to_timecode(ts_in, framerate)
        tc_out = timestamp_to_timecode(ts_out, framerate)
        end = tc_indices[idx + 1] if idx + 1 < len(tc_indices) else line_count
        cap_lines = []
        for j in range(i + 1, end):
            cap = lines[j].strip()
            if not cap:
                break
            cap_lines.append(cap)
        blocks.append(CaptionBlock(tc_in, tc_out, cap_lines))
    return blocks


def write_amc(blocks):
    out = []
    out.append("@ This file written with the Avid Caption plugin, version 1\n")
    out.append("\n")
    out.append("<begin subtitles>\n")
    for b in blocks:
        out.append(f"{b.timecode_in} {b.timecode_out}\n")
        for line in b.lines:
            out.append(f"{line}\n")
        out.append("\n")
    out.append("<end subtitles>\n")
    return out


def write_csv(blocks, quotechar):
    out = []
    for b in blocks:
        out.append(_csv_write_row([b.timecode_in, b.timecode_out] + b.lines, quotechar))
    return out


def write_pr(blocks):
    out = []
    for b in blocks:
        out.append(f"{b.timecode_in} - {b.timecode_out}\n")
        for line in b.lines:
            out.append(f"{line}\n")
        out.append("\n")
    return out


def write_srt(blocks, framerate):
    out = []
    for i, b in enumerate(blocks):
        ts_in = timecode_to_timestamp(b.timecode_in, framerate)
        ts_out = timecode_to_timestamp(b.timecode_out, framerate)
        out.append(f"{i + 1}\n")
        out.append(f"{ts_in} --> {ts_out}\n")
        for line in b.lines:
            out.append(f"{line}\n")
        out.append("\n")
    return out


def write_md(blocks):
    out = []
    for b in blocks:
        out.append(_md_table_row([b.timecode_in, b.timecode_out] + b.lines))
    return out


def read_md(lines):
    blocks = []
    tc_re = re.compile(r"\d\d:\d\d:\d\d[:;]\d\d")
    sep_re = re.compile(r"^\|[\s\-:]+\|")
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("|"):
            continue
        if sep_re.match(stripped):
            continue
        cells = re.split(r"(?<!\\)\|", stripped)
        cells = [c.strip() for c in cells[1:-1]]
        if len(cells) < 2:
            continue
        if not tc_re.match(cells[0]):
            continue
        cells = [c.replace("\\|", "|").replace("<br>", "\n") for c in cells]
        blocks.append(CaptionBlock(cells[0], cells[1], cells[2:]))
    return blocks


def detect_framerate(input_lines):
    candidates = [24, 25, 30, 48, 50, 60]
    ts_re = re.compile(r",(\d{3})")
    ms_set = set()
    for line in input_lines:
        for ms_str in ts_re.findall(line):
            ms_set.add(int(ms_str))
            if len(ms_set) >= 8:
                break
        if len(ms_set) >= 8:
            break
    ms_values = list(ms_set)
    if len(ms_values) <= 1:
        return 25, False
    best, best_score = 25, float("inf")
    for fr in candidates:
        dur = 1000 / fr
        wrapped = [min(v % dur, dur - v % dur) for v in ms_values]
        penalty = sum(w * w for w in wrapped) / len(wrapped)
        if penalty < best_score:
            best, best_score = fr, penalty
    if best_score > 4.0:
        return 25, False
    return best, True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", nargs="?", default=None)
    parser.add_argument("output_file", nargs="?", default=None)
    parser.add_argument("-i", "--input", action="append", dest="input_files")
    parser.add_argument("-o", "--output", default=None, dest="output_file_flag")
    parser.add_argument("-tl", "--tolerance", type=int, default=0)
    parser.add_argument("-if", "--inputformat", choices=["avid", "csv", "pr", "srt", "md"])
    parser.add_argument("-of", "--outputformat", action="append",
                        choices=["avid", "csv", "pr", "srt", "md"])
    parser.add_argument("-m", "--splitmulti", type=int, default=None)
    parser.add_argument("-r", "--framerate", type=float, default=None)
    parser.add_argument("-f", "--fromtimecode", default="00:00:00:00")
    parser.add_argument("-t", "--totimecode", default="00:00:00:00")
    parser.add_argument("-df", "--dropframe", action="store_const", const=True)
    parser.add_argument("-D", "--decoder", default="utf-8-sig")
    parser.add_argument("-qr", "--quoteread", nargs="?", const="PROMPT")
    parser.add_argument("-qw", "--quotewrite", nargs="?", const="PROMPT")
    args = parser.parse_args()

    input_files = args.input_files or ([args.input_file] if args.input_file else [])
    output_file = args.output_file_flag or args.output_file

    if not input_files:
        print("Error: no input file specified")
        sys.exit(2)

    if not args.outputformat and not output_file:
        print("Please specify either an output file name or the output file format.")
        sys.exit()

    if len(input_files) > 2:
        print("Error: combine mode supports exactly 2 input files")
        sys.exit(2)

    decoder = args.decoder
    input_file_type = ""
    sof_string = "----------------Start of File----------------"
    eof_string = "----------------End of File----------------"

    if args.quotewrite is not None:
        if args.quotewrite == "PROMPT":
            CSV_QUOTE_OUT = input("Enter write quote character [\\]: ").strip() or '\\'
        else:
            CSV_QUOTE_OUT = args.quotewrite

    if args.quoteread is not None:
        if args.quoteread == "PROMPT":
            CSV_QUOTE_IN = input("Enter read quote character [\\]: ").strip() or '\\'
        else:
            CSV_QUOTE_IN = args.quoteread

    origin_tc = args.fromtimecode
    target_tc = args.totimecode

    input_file_type = ""
    if len(input_files) == 1:
        input_file = input_files[0]
        try:
            input_base_dir_pair = os.path.splitext(input_file)
        except os.error as err:
            print(str(err))
            sys.exit(2)
        try:
            o = open(input_file, "r", encoding=args.decoder)
        except FileNotFoundError:
            print("Input file not found!")
            sys.exit(2)
        else:
            with o as read_file:
                input_lines = read_file.readlines()

        if args.quoteread is None:
            for line in input_lines:
                stripped = line.strip()
                if stripped:
                    CSV_QUOTE_IN = '"' if stripped.startswith('"') else '\\'
                    break

        if input_base_dir_pair[1] == ".txt":
            if args.inputformat is None:
                print(
                    "Please define the type of the input txt file with [-if|--inputformat] argument\n",
                    "Supported types are avid, csv, pr, srt and md",
                )
                sys.exit()
            else:
                input_file_type = args.inputformat
        elif input_base_dir_pair[1] == ".csv":
            input_file_type = "csv"
        elif input_base_dir_pair[1] == ".srt":
            input_file_type = "srt"
        elif input_base_dir_pair[1] == ".md":
            input_file_type = "md"
        else:
            print(
                "Input file format not supported\n Supported formats are csv, srt, md and txt"
            )
            sys.exit()

        # Determine framerate
        framerate_messages = []
        overlap_msgs = []
        if input_file_type == "srt":
            detected, ok = detect_framerate(input_lines)
            if args.framerate is not None:
                framerate = args.framerate
                if framerate != detected:
                    framerate_messages.append(f"\033[33mWarning: auto-detected {detected}fps, using {framerate}fps\033[0m")
                else:
                    framerate_messages.append(f"\033[32mAuto-detected framerate: {framerate}fps (matches -r)\033[0m")
            else:
                framerate = detected
                if ok:
                    framerate_messages.append(f"\033[32mAuto-detected framerate: {framerate}fps\033[0m")
                else:
                    framerate_messages.append(f"\033[33mCould not detect framerate, defaulting to {framerate}fps\033[0m")
        else:
            framerate = args.framerate or 25
            framerate_messages = []
            if args.framerate is None:
                framerate_messages.append(f"\033[36mUsed framerate: {framerate}fps\033[0m")
            else:
                framerate_messages.append(f"\033[36mUsed framerate: {framerate}fps\033[0m")

        if args.dropframe is None:
            if framerate in [29.97, 59.94]:
                while True:
                    drop_frame_input = (
                        input("Use drop-frame timecode (y/n, default n)): \n")
                        .strip()
                        .lower()
                        or "n"
                    )
                    if drop_frame_input == "y":
                        drop_frame = True
                        break
                    elif drop_frame_input == "n":
                        drop_frame = False
                        break
            else:
                drop_frame = False
        else:
            drop_frame = args.dropframe

        offset_frames = timecode_to_frames(target_tc, framerate, drop_frame) - timecode_to_frames(
            origin_tc, framerate, drop_frame
        )

        # Define output file name
        if output_file is not None:
            try:
                output_base_dir_pair = os.path.splitext(output_file)
            except os.error as err:
                print(str(err))
                sys.exit(2)
            if origin_tc == target_tc:
                output_base_name = output_base_dir_pair[0]
            else:
                output_base_name = (
                    output_base_dir_pair[0]
                    + "_alignedTo_"
                    + target_tc[0:2]
                    + "-"
                    + target_tc[3:5]
                    + "-"
                    + target_tc[6:8]
                    + "-"
                    + target_tc[9:11]
                    + "_"
                    + str(framerate)
                    + "FPS"
                )
        else:
            if origin_tc == target_tc:
                output_base_name = input_base_dir_pair[0]
            else:
                if re.match(r".*_alignedTo_\d\d-\d\d-\d\d-\d\d_", input_base_dir_pair[0]):
                    output_base_name = (
                        re.split(r"_alignedTo_", input_base_dir_pair[0], 1)[0]
                        + "_alignedTo_"
                        + target_tc[0:2]
                        + "-"
                        + target_tc[3:5]
                        + "-"
                        + target_tc[6:8]
                        + "-"
                        + target_tc[9:11]
                        + "_"
                        + str(framerate)
                        + "FPS"
                    )
                else:
                    output_base_name = (
                        input_base_dir_pair[0]
                        + "_alignedTo_"
                        + target_tc[0:2]
                        + "-"
                        + target_tc[3:5]
                        + "-"
                        + target_tc[6:8]
                        + "-"
                        + target_tc[9:11]
                        + "_"
                        + str(framerate)
                        + "FPS"
                    )

        # Parse input into blocks
        if input_file_type == "avid":
            blocks = read_amc(input_lines)
        elif input_file_type == "csv":
            blocks = read_csv(input_lines, CSV_QUOTE_IN)
        elif input_file_type == "pr":
            blocks = read_pr(input_lines)
        elif input_file_type == "srt":
            blocks = read_srt(input_lines, framerate)
        elif input_file_type == "md":
            blocks = read_md(input_lines)
        else:
            print("Unknown input format")
            sys.exit(2)

    else:
        # Combine mode (2 files)
        file1, file2 = input_files[0], input_files[1]
        file1_ext = os.path.splitext(file1)[1]
        if file1_ext == ".txt":
            if args.inputformat is None:
                print(
                    "Please define the type of the input txt file with [-if|--inputformat] argument\n",
                    "Supported types are avid, csv, pr, srt and md",
                )
                sys.exit()
            else:
                input_file_type = args.inputformat
        elif file1_ext == ".csv":
            input_file_type = "csv"
        elif file1_ext == ".srt":
            input_file_type = "srt"
        elif file1_ext == ".md":
            input_file_type = "md"
        else:
            print("Input file format not supported")
            sys.exit(2)

        try:
            with open(file1, "r", encoding=args.decoder) as f:
                lines1 = f.readlines()
            with open(file2, "r", encoding=args.decoder) as f:
                lines2 = f.readlines()
        except FileNotFoundError:
            print("Input file not found!")
            sys.exit(2)

        if args.quoteread is None:
            for line in lines1:
                stripped = line.strip()
                if stripped:
                    CSV_QUOTE_IN = '"' if stripped.startswith('"') else '\\'
                    break

        framerate_messages = []
        if args.framerate is not None:
            framerate = args.framerate
        elif input_file_type == "srt":
            detected, ok = detect_framerate(lines1)
            framerate = detected
            if ok:
                framerate_messages.append(f"\033[32mAuto-detected framerate: {framerate}fps\033[0m")
            else:
                framerate_messages.append(f"\033[33mCould not detect framerate, defaulting to {framerate}fps\033[0m")
        else:
            framerate = 25
        framerate_messages.append(f"\033[36mUsed framerate: {framerate}fps\033[0m")

        if args.dropframe is None:
            drop_frame = False
        else:
            drop_frame = args.dropframe

        offset_frames = timecode_to_frames(target_tc, framerate, drop_frame) - timecode_to_frames(
            origin_tc, framerate, drop_frame
        )

        if output_file is None:
            print("Error: -o required for combine mode")
            sys.exit(2)
        output_base_dir_pair = os.path.splitext(output_file)
        if origin_tc == target_tc:
            output_base_name = output_base_dir_pair[0]
        else:
            output_base_name = (
                output_base_dir_pair[0]
                + "_alignedTo_"
                + target_tc[0:2]
                + "-"
                + target_tc[3:5]
                + "-"
                + target_tc[6:8]
                + "-"
                + target_tc[9:11]
                + "_"
                + str(framerate)
                + "FPS"
            )

        if input_file_type == "avid":
            blocks1 = read_amc(lines1)
            blocks2 = read_amc(lines2)
        elif input_file_type == "csv":
            blocks1 = read_csv(lines1, CSV_QUOTE_IN)
            blocks2 = read_csv(lines2, CSV_QUOTE_IN)
        elif input_file_type == "pr":
            blocks1 = read_pr(lines1)
            blocks2 = read_pr(lines2)
        elif input_file_type == "srt":
            blocks1 = read_srt(lines1, framerate)
            blocks2 = read_srt(lines2, framerate)
        elif input_file_type == "md":
            blocks1 = read_md(lines1)
            blocks2 = read_md(lines2)
        else:
            print("Unknown input format")
            sys.exit(2)

        set_frame_numbers(blocks1, framerate, drop_frame)
        set_frame_numbers(blocks2, framerate, drop_frame)
        blocks, overlap_msgs = merge_blocks(blocks1, blocks2, framerate, drop_frame, args.tolerance)

    # Determine language count
    detected = max((len(b.lines) for b in blocks), default=1)

    if args.splitmulti is not None:
        if args.splitmulti < detected:
            print(
                f"Warning: data has {detected} languages, "
                f"splitting into {args.splitmulti} files; excess lines joined"
            )
        target = args.splitmulti
        if target > detected:
            pad_blocks(blocks, target)
        do_split = target >= 2
    else:
        target = 1
        do_split = False

    # Align timecodes once
    if origin_tc != target_tc:
        align_blocks(blocks, offset_frames, framerate, drop_frame)

    # Determine output formats
    if args.outputformat:
        output_formats = args.outputformat
    else:
        if output_base_dir_pair[1] in (".txt", ""):
            print(
                "Please define the type of the output txt file "
                "with [-of|--outputformat] argument\n"
                "Supported types are avid, csv, pr, srt and md",
            )
            sys.exit()
        elif output_base_dir_pair[1] == ".csv":
            output_formats = ["csv"]
        elif output_base_dir_pair[1] == ".srt":
            output_formats = ["srt"]
        elif output_base_dir_pair[1] == ".md":
            output_formats = ["md"]
        else:
            print("Defined output file extension not supported")
            sys.exit()

    ext_map = {"avid": ".txt", "csv": ".csv", "pr": ".txt", "srt": ".srt", "md": ".md"}

    for fmt in output_formats:
        ext = ext_map[fmt]
        if do_split:
            for lang in range(target):
                output_file = output_base_name + "_L" + str(lang + 1) + ext
                print(f"\n\n\nWriting L{lang + 1} to {output_file}\n\n{sof_string}")
                split = split_blocks(blocks, lang, target)
                output_lines = []
                if fmt == "md":
                    output_lines.append(f"# {output_base_name}_L{lang + 1}\n\n")
                if fmt == "avid":
                    output_lines += write_amc(split)
                elif fmt == "csv":
                    output_lines += write_csv(split, CSV_QUOTE_OUT)
                elif fmt == "pr":
                    output_lines += write_pr(split)
                elif fmt == "srt":
                    output_lines += write_srt(split, framerate)
                elif fmt == "md":
                    output_lines += write_md(split)
                with open(output_file, "w", encoding=decoder) as f:
                    for line in output_lines:
                        print(line, end="")
                f.writelines(output_lines)
            print(eof_string)
        else:
            output_file = output_base_name + ext
            print(f"\n\n\nWriting to {output_file}\n\n{sof_string}")
            output_lines = []
            if fmt == "md":
                output_lines.append(f"# {output_base_name}\n\n")
            if fmt == "avid":
                output_lines += write_amc(blocks)
            elif fmt == "csv":
                output_lines += write_csv(blocks, CSV_QUOTE_OUT)
            elif fmt == "pr":
                output_lines += write_pr(blocks)
            elif fmt == "srt":
                output_lines += write_srt(blocks, framerate)
            elif fmt == "md":
                output_lines += write_md(blocks)
            with open(output_file, "w", encoding=decoder) as f:
                for line in output_lines:
                    print(line, end="")
                f.writelines(output_lines)
            print(eof_string)

    for msg in framerate_messages:
        print(msg)
    for msg in overlap_msgs:
        print(msg)
