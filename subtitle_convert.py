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


def timecodeToFrames(tcString, framerate, dropFrame=False):
    tcString = tcString.strip()
    tcHH, tcMM, tcSS, tcFF = (
        int(tcString[0:2]),
        int(tcString[3:5]),
        int(tcString[6:8]),
        int(tcString[9:11]),
    )
    timeBase = round(framerate)
    if not dropFrame:
        frameNumber = tcFF + (((tcHH * 60 + tcMM) * 60) + tcSS) * timeBase
    else:
        totalMinutes = tcHH * 60 + tcMM
        framesDropped = round(framerate * 2 / 30)
        frameNumber = (
            (totalMinutes * 60 + tcSS) * timeBase
            + tcFF
            - (framesDropped * (totalMinutes - totalMinutes // 10))
        )
    return frameNumber


def framesToTimecode(frameNumber, framerate, dropFrame=False):
    timeBase = round(framerate)
    if not dropFrame:
        tcFF = int(frameNumber % timeBase)
        totalSeconds = frameNumber // timeBase
        tcHH = int(totalSeconds // 3600)
        tcMM = int((totalSeconds - tcHH * 3600) // 60)
        tcSS = int(totalSeconds % 60)
        tcString = (
            str(tcHH).zfill(2)
            + ":"
            + str(tcMM).zfill(2)
            + ":"
            + str(tcSS).zfill(2)
            + ":"
            + str(tcFF).zfill(2)
        )
    else:
        framesDropped = round(framerate * 2 / 30)
        framesTenMinutes = round(framerate * 600)
        framesPerMinute = round(framerate) * 60 - framesDropped
        d = frameNumber // framesTenMinutes
        m = frameNumber % framesTenMinutes
        if m > framesDropped:
            frameNumber = (
                frameNumber
                + framesDropped * 9 * d
                + framesDropped * ((m - framesDropped) // framesPerMinute)
            )
        else:
            frameNumber = frameNumber + framesDropped * 9 * d
        tcHH = ((frameNumber // timeBase) // 60) // 60
        tcMM = ((frameNumber // timeBase) // 60) % 60
        tcSS = (frameNumber // timeBase) % 60
        tcFF = frameNumber % timeBase
        tcString = (
            str(tcHH).zfill(2)
            + ":"
            + str(tcMM).zfill(2)
            + ":"
            + str(tcSS).zfill(2)
            + ";"
            + str(tcFF).zfill(2)
        )
    return tcString


def timecodeToSrtTimestamp(tcString, framerate):
    frameDur = 1000 / framerate
    tcHH, tcMM, tcSS, tcFF = (
        int(tcString[0:2]),
        int(tcString[3:5]),
        int(tcString[6:8]),
        int(tcString[9:11]),
    )
    srtMS = str(int(int(tcFF) * frameDur)).zfill(3)
    srtTimestamp = (
        str(tcHH).zfill(2)
        + ":"
        + str(tcMM).zfill(2)
        + ":"
        + str(tcSS).zfill(2)
        + ","
        + srtMS
    )
    return srtTimestamp


def srtTimestampToTimecode(srtTimestamp, framerate):
    frameDur = 1000 / framerate
    tcHH, tcMM, srtSSMS = srtTimestamp.split(":")
    tcSS, srtMS = srtSSMS.split(",")
    tcFF = round(int(srtMS) / frameDur)
    tcString = tcHH + ":" + tcMM + ":" + tcSS + ":" + str(tcFF).zfill(2)
    return tcString


def timecodeAlign(sourceTimecode, framesDiff, framerate, dropFrame=False):
    targetFramesCount = (
        timecodeToFrames(sourceTimecode, framerate, dropFrame) + framesDiff
    )
    return framesToTimecode(targetFramesCount, framerate, dropFrame)


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
        b.timecode_in = timecodeAlign(b.timecode_in, offset_frames, framerate, drop_frame)
        b.timecode_out = timecodeAlign(b.timecode_out, offset_frames, framerate, drop_frame)
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
        srt_in, srt_out = lines[i].strip().split(" --> ")
        tc_in = srtTimestampToTimecode(srt_in, framerate)
        tc_out = srtTimestampToTimecode(srt_out, framerate)
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
        srt_in = timecodeToSrtTimestamp(b.timecode_in, framerate)
        srt_out = timecodeToSrtTimestamp(b.timecode_out, framerate)
        out.append(f"{i + 1}\n")
        out.append(f"{srt_in} --> {srt_out}\n")
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
    parser.add_argument("-s", "--splitsingle", type=int)
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

    operationMode = []
    outputFileSet = 0
    explicitMode = 1
    decoder = args.decoder
    inputFileType = ""
    splitCount = 1
    sofString = "----------------Start of File----------------"
    eofString = "----------------End of File----------------"

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

    originTC = args.fromtimecode
    targetTC = args.totimecode
    framerate = args.framerate
    if args.dropframe is None:
        if framerate in [29.97, 59.94]:
            while True:
                dropFrameInput = (
                    input("Use drop-frame timecode (y/n, default n)): \n")
                    .strip()
                    .lower()
                    or "n"
                )
                if dropFrameInput == "y":
                    dropFrame = True
                    break
                elif dropFrameInput == "n":
                    dropFrame = False
                    break
        else:
            dropFrame = False
    else:
        dropFrame = args.dropframe

    offsetFrames = timecodeToFrames(targetTC, framerate, dropFrame) - timecodeToFrames(
        originTC, framerate, dropFrame
    )
    srtOffsetFrames = 0 - timecodeToFrames(originTC, framerate, dropFrame)

    inputFile = args.input_file
    try:
        inputBaseDirPair = os.path.splitext(inputFile)
    except os.error as err:
        print(str(err))
        sys.exit(2)
    try:
        o = open(inputFile, "r", encoding=args.decoder)
    except FileNotFoundError:
        print("Input file not found!")
        sys.exit(2)
    else:
        with o as readFile:
            inputLines = readFile.readlines()

    if args.quoteread is None:
        for line in inputLines:
            stripped = line.strip()
            if stripped:
                CSV_QUOTE_IN = '"' if stripped.startswith('"') else '\\'
                break

    if inputBaseDirPair[1] == ".txt":
        if args.inputformat is None:
            print(
                "Please define the type of the input txt file with [-if|--inputformat] argument\n",
                "Supported types are avid, csv, pr, srt and md",
            )
            sys.exit()
        else:
            inputFileType = args.inputformat
    elif inputBaseDirPair[1] == ".csv":
        inputFileType = "csv"
    elif inputBaseDirPair[1] == ".srt":
        inputFileType = "srt"
    else:
        print(
            "Input file format not supported\n Supported formats are csv, srt and txt"
        )
        sys.exit()

    # Define output file name
    if args.output_file is not None:
        try:
            outputBaseDirPair = os.path.splitext(args.output_file)
        except os.error as err:
            print(str(err))
            sys.exit(2)
        if originTC == targetTC:
            outputBaseName = outputBaseDirPair[0]
        else:
            outputBaseName = (
                outputBaseDirPair[0]
                + "_alignedTo_"
                + targetTC[0:2]
                + "-"
                + targetTC[3:5]
                + "-"
                + targetTC[6:8]
                + "-"
                + targetTC[9:11]
                + "_"
                + str(framerate)
                + "FPS"
            )
    else:
        if originTC == targetTC:
            outputBaseName = inputBaseDirPair[0]
        else:
            if re.match(r".*_alignedTo_\d\d-\d\d-\d\d-\d\d_", inputBaseDirPair[0]):
                outputBaseName = (
                    re.split(r"_alignedTo_", inputBaseDirPair[0], 1)[0]
                    + "_alignedTo_"
                    + targetTC[0:2]
                    + "-"
                    + targetTC[3:5]
                    + "-"
                    + targetTC[6:8]
                    + "-"
                    + targetTC[9:11]
                    + "_"
                    + str(framerate)
                    + "FPS"
                )
            else:
                outputBaseName = (
                    inputBaseDirPair[0]
                    + "_alignedTo_"
                    + targetTC[0:2]
                    + "-"
                    + targetTC[3:5]
                    + "-"
                    + targetTC[6:8]
                    + "-"
                    + targetTC[9:11]
                    + "_"
                    + str(framerate)
                    + "FPS"
                )

    # Parse input into blocks
    if inputFileType == "avid":
        blocks = read_amc(inputLines)
    elif inputFileType == "csv":
        blocks = read_csv(inputLines, CSV_QUOTE_IN)
    elif inputFileType == "pr":
        blocks = read_pr(inputLines)
    elif inputFileType == "srt":
        blocks = read_srt(inputLines, framerate)
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
    if originTC != targetTC:
        align_blocks(blocks, offsetFrames, framerate, dropFrame)

    # Determine output formats
    if args.outputformat:
        output_formats = args.outputformat
    else:
        if outputBaseDirPair[1] in (".txt", ""):
            print(
                "Please define the type of the output txt file "
                "with [-of|--outputformat] argument\n"
                "Supported types are avid, csv, pr, srt and md",
            )
            sys.exit()
        elif outputBaseDirPair[1] == ".csv":
            output_formats = ["csv"]
        elif outputBaseDirPair[1] == ".srt":
            output_formats = ["srt"]
        elif outputBaseDirPair[1] == ".md":
            output_formats = ["md"]
        else:
            print("Defined output file extension not supported")
            sys.exit()

    ext_map = {"avid": ".txt", "csv": ".csv", "pr": ".txt", "srt": ".srt", "md": ".md"}

    for fmt in output_formats:
        ext = ext_map[fmt]
        if do_split:
            for lang in range(target):
                outputFile = outputBaseName + "_L" + str(lang + 1) + ext
                print(f"\n\n\nWriting L{lang + 1} to {outputFile}\n\n{sofString}")
                split = split_blocks(blocks, lang, target)
                outputLines = []
                if fmt == "md":
                    outputLines.append(f"# {outputBaseName}_L{lang + 1}\n\n")
                if fmt == "avid":
                    outputLines += write_amc(split)
                elif fmt == "csv":
                    outputLines += write_csv(split, CSV_QUOTE_OUT)
                elif fmt == "pr":
                    outputLines += write_pr(split)
                elif fmt == "srt":
                    outputLines += write_srt(split, framerate)
                elif fmt == "md":
                    outputLines += write_md(split)
                with open(outputFile, "w", encoding=decoder) as f:
                    f.writelines(outputLines)
                print(eofString)
        else:
            outputFile = outputBaseName + ext
            print(f"\n\n\nWriting to {outputFile}\n\n{sofString}")
            outputLines = []
            if fmt == "md":
                outputLines.append(f"# {outputBaseName}\n\n")
            if fmt == "avid":
                outputLines += write_amc(blocks)
            elif fmt == "csv":
                outputLines += write_csv(blocks, CSV_QUOTE_OUT)
            elif fmt == "pr":
                outputLines += write_pr(blocks)
            elif fmt == "srt":
                outputLines += write_srt(blocks, framerate)
            elif fmt == "md":
                outputLines += write_md(blocks)
            with open(outputFile, "w", encoding=decoder) as f:
                f.writelines(outputLines)
            print(eofString)
