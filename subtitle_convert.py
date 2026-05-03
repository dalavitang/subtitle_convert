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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("output_file", nargs="?", default=None)
    parser.add_argument("-if", "--inputformat", choices=["avid", "csv", "pr", "srt"])
    parser.add_argument("-of", "--outputformat", action="append",
                        choices=["avid", "csv", "pr", "srt", "md"])
    parser.add_argument("-m", "--splitmulti", type=int, default=None)
    parser.add_argument("-r", "--framerate", type=float, default=25)
    parser.add_argument("-f", "--fromtimecode", default="00:00:00:00")
    parser.add_argument("-t", "--totimecode", default="00:00:00:00")
    parser.add_argument("-df", "--dropframe", action="store_const", const=True)
    parser.add_argument("-D", "--decoder", default="utf-8-sig")
    parser.add_argument("-qr", "--quoteread", nargs="?", const="PROMPT")
    parser.add_argument("-qw", "--quotewrite", nargs="?", const="PROMPT")
    args = parser.parse_args()

    if not args.outputformat and args.output_file is None:
        print("Please specify either an output file name or the output file format.")
        sys.exit()

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
    framerate = args.framerate
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

    input_file = args.input_file
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
    else:
        print(
            "Input file format not supported\n Supported formats are csv, srt and txt"
        )
        sys.exit()

    # Define output file name
    if args.output_file is not None:
        try:
            output_base_dir_pair = os.path.splitext(args.output_file)
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
    else:
        print("Unknown input format")
        sys.exit(2)

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
