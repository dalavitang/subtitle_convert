import getopt, argparse, sys, os, re

def timecodeToFrames(tcString,framerate,dropFrame=False):
    tcString = tcString.strip()
    tcHH, tcMM, tcSS, tcFF = int(tcString[0:2]), int(tcString[3:5]), int(tcString[6:8]), int(tcString[9:11])
    timeBase = round(framerate)
    if not dropFrame:
        frameNumber = tcFF + (((tcHH * 60 + tcMM) * 60) + tcSS) * timeBase
    else:
        totalMinutes = tcHH * 60 + tcMM
        framesDropped = round(framerate * 2 / 30)
        frameNumber = (totalMinutes * 60 + tcSS) * timeBase + tcFF - (framesDropped * (totalMinutes - totalMinutes // 10))
    return frameNumber

def framesToTimecode(frameNumber,framerate,dropFrame=False):
    timeBase = round(framerate)
    if not dropFrame:
        tcFF = int(frameNumber % timeBase)
        totalSeconds = frameNumber // timeBase
        tcHH = int(totalSeconds // 3600)
        tcMM = int((totalSeconds - tcHH * 3600) // 60)
        tcSS = int(totalSeconds % 60)
        tcString = str(tcHH).zfill(2) + ':' + str(tcMM).zfill(2) + ':' + str(tcSS).zfill(2) + ':' + str(tcFF).zfill(2)
    else:
        framesDropped = round(framerate * 2 / 30)
        framesPerHour = round(framerate * 3600)
        framesTenMinutes = round(framerate * 600)
        framesPerMinute = round(framerate) * 60 - framesDropped
        d = frameNumber // framesTenMinutes
        m = frameNumber % framesTenMinutes
        if m > framesDropped:
            frameNumber = frameNumber + framesDropped * 9 * d + framesDropped * ((m - framesDropped) // framesPerMinute)
        else:
            frameNumber = frameNumber + framesDropped * 9 * d
        tcHH = ((frameNumber // timeBase) // 60) // 60
        tcMM = ((frameNumber // timeBase) // 60) % 60
        tcSS = (frameNumber // timeBase) % 60
        tcFF = frameNumber % timeBase
        tcString = str(tcHH).zfill(2) + ':' + str(tcMM).zfill(2) + ':' + str(tcSS).zfill(2) + ';' + str(tcFF).zfill(2)
    return tcString

def timecodeToSrtTimestamp(tcString,framerate):
    tcHH, tcMM, tcSS, tcFF = int(tcString[0:2]), int(tcString[3:5]), int(tcString[6:8]), int(tcString[9:11])
    srtMS = str(int(int(tcFF)/framerate*1000)).zfill(3)
    srtTimestamp = tcHH + ':' + tcMM + ':' + tcSS + ',' + srtMS
    return srtTimestamp

def srtTimestampToTimecode(srtTimestamp,framerate):
    tcHH, tcMM, srtSSMS = srtTimestamp.split(':')
    tcSS, srtMS = srtSSMS.split(',')
    tcFF = int(int(srtMS) / 1000 * framerate)
    tcString = tcHH + ':' + tcMM + ':' + tcSS + ':' + str(tcFF).zfill(2)
    return tcString

def timecodeAlign(sourceTimecode,framesDiff,framerate,dropFrame=False):
    targetFramesCount = timecodeToFrames(sourceTimecode,framerate,dropFrame) + framesDiff
    return framesToTimecode(targetFramesCount,framerate,dropFrame)

def amcAlign(inputSubcapLines,offsetFrames,framerate,dropFrame):
    outputSubcapLines = []
    for inputLine in inputSubcapLines:
        if re.match(r'^\d\d:\d\d:\d\d[:;]\d\d\s\d\d:\d\d:\d\d[:;]\d\d',inputLine):
            sourceTimecodeIn, sourceTimecodeOut = inputLine.split()
            timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
            timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
            outputLine = timecodeIn + ' ' + timecodeOut + '\n'
            print(outputLine,end='')
            outputSubcapLines.append(outputLine)
        else:
            outputLine = inputLine
            print(outputLine,end='')
            outputSubcapLines.append(outputLine)
    return outputSubcapLines

def amcToSrt(inputSubcapLines,srtOffsetFrames,framerate):
    outputSrtLines = []
    for i in range(3,len(inputSubcapLines)-2,3):
        index = int(i // 3)
        sourceTimecode = inputSubcapLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut = sourceTimecode.split()
        captionText = inputSubcapLines[i+1].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,srtOffsetFrames,framerate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,srtOffsetFrames,framerate)
        timecodeInSrt = timecodeToSrtTimestamp(timecodeIn,framerate)
        timecodeOutSrt = timecodeToSrtTimestamp(timecodeOut,framerate)
        timecodeSrt = timecodeInSrt + ' --> ' + timecodeOutSrt
        print(f'{str(index)}\n{timecodeSrt}\n{captionText}\n')
        outputSrtLines.append(f'{str(index)}\n')
        outputSrtLines.append(f'{timecodeSrt}\n')
        outputSrtLines.append(f'{captionText}\n')
        outputSrtLines.append(f'\n')
    return outputSrtLines

def amcToCsv(inputSubcapLines,offsetFrames,framerate,dropFrame):
    outputCsvLines = []
    for i in range(3,len(inputSubcapLines)-2,3):
        sourceTimecode = inputSubcapLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut = sourceTimecode.split()
        captionText = inputSubcapLines[i+1].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def amcSplitCsv(inputSubcapLines,offsetFrames,languageCount,languageIndex,framerate,dropFrame):
    outputCsvLines = []
    for i in range(3,len(inputSubcapLines)-2, 2 + languageCount):
        sourceTimecodeIn, sourceTimecodeOut = inputSubcapLines[i].strip().split()
        captionText = inputSubcapLines[i + 1 + languageIndex].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def csvAlign(inputCsvLines,offsetFrames,framerate,dropFrame):
    outputCsvLines = []
    for i in range(0,len(inputCsvLines)):
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        captionText = captionText.strip('"')
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def csvToSrt(inputCsvLines,srtOffsetFrames,framerate):
    outputSrtLines = []
    for i in range(0,len(inputCsvLines)):
        index = i + 1
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        timecodeIn = timecodeAlign(sourceTimecodeIn,srtOffsetFrames,framerate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,srtOffsetFrames,framerate)
        timecodeInSrt = timecodeToSrtTimestamp(timecodeIn,framerate)
        timecodeOutSrt = timecodeToSrtTimestamp(timecodeOut,framerate)
        timecodeSrt = timecodeInSrt + ' --> ' + timecodeOutSrt
        captionText = captionText.strip('"')
        print(f'{str(index)}\n{timecodeSrt}\n{captionText}\n')
        outputSrtLines.append(f'{str(index)}\n')
        outputSrtLines.append(f'{timecodeSrt}\n')
        outputSrtLines.append(f'{captionText}\n')
        outputSrtLines.append(f'\n')
    return outputSrtLines

def csvToAmc(inputCsvLines,offsetFrames,framerate,dropFrame):
    outputSubcapLines = []
    amcStart = '@ This file written with the Avid Caption plugin, version 1\n\n<begin subtitles>\n'
    amcEnd = '<end subtitles>\n'
    print(amcStart,end='')
    outputSubcapLines.append(amcStart)
    for i in range(0,len(inputCsvLines)):
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        captionText = captionText.strip('"')
        tcString = timecodeIn + ' ' + timecodeOut
        print(f'{tcString}\n{captionText}\n')
        outputSubcapLines.append(f'{tcString}\n')
        outputSubcapLines.append(f'{captionText}\n')
        outputSubcapLines.append(f'\n')
    print(amcEnd,end='')
    outputSubcapLines.append(amcEnd)
    return outputSubcapLines

def srtToAmc(inputSrtLines,offsetFrames,framerate):
    outputSubcapLines = []
    amcStart = '@ This file written with the Avid Caption plugin, version 1\n\n<begin subtitles>\n'
    amcEnd = '<end subtitles>\n'
    print(amcStart,end='')
    outputSubcapLines.append(amcStart)
    for i in range(0, len(inputSrtLines), 4):
        srtTimestampIn, srtTimestampOut = inputSrtLines[i + 1].strip().split(' --> ')
        captionText = inputSrtLines[i + 2].strip()
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,framerate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,framerate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate)
        tcString = timecodeIn + ' ' + timecodeOut
        print(f'{tcString}\n{captionText}\n')
        outputSubcapLines.append(f'{tcString}\n')
        outputSubcapLines.append(f'{captionText}\n')
        outputSubcapLines.append(f'\n')
    print(amcEnd,end='')
    outputSubcapLines.append(amcEnd)
    return outputSubcapLines

def srtToCsv(inputSrtLines,offsetFrames,framerate):
    outputCsvLines = []
    ll = len(inputSrtLines)
    timecodeIndicies = [i for i in range(ll) \
        if re.match(r'^\d\d.\d\d.\d\d.\d\d\d --> \d\d.\d\d.\d\d.\d\d\d\n', inputSrtLines[i])]
    il = len(timecodeIndicies)
    for i in range(il):
        index = timecodeIndicies[i]
        if i == il - 1:
            segmentLen = ll - timecodeIndicies[i] + 1
        else:
            segmentLen = timecodeIndicies[i+1] - timecodeIndicies[i]
        srtTimestampIn, srtTimestampOut = inputSrtLines[index].strip().split(' --> ')
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,framerate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,framerate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate)
        captionBlock = ''
        for j in range(1,segmentLen - 2):
            if j == segmentLen - 2 - 1:
                captionBlock += inputSrtLines[index+j].strip()
            else:
                captionBlock += inputSrtLines[index+j]
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionBlock + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def srtSplitCsv(inputSrtLines,offsetFrames,framerate,languageCount,languageIndex):
    outputCsvLines = []
    for i in range(0, len(inputSrtLines), 3 + languageCount):
        srtTimestampIn, srtTimestampOut = inputSrtLines[i + 1].strip().split(' --> ')
        captionText = inputSrtLines[i + 2 + languageIndex].strip()
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,framerate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,framerate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def prToCsv(inputTxtLines,offsetFrames,framerate,dropFrame):
    outputCsvLines = []
    ll = len(inputTxtLines)
    timecodeIndicies = [i for i in range(ll) \
        if re.match(r'^\d\d.\d\d.\d\d.\d\d - \d\d.\d\d.\d\d.\d\d\n', inputTxtLines[i])]
    il = len(timecodeIndicies)
    for i in range(il):
        index = timecodeIndicies[i]
        if i == il - 1:
            segmentLen = ll - timecodeIndicies[i] + 1
        else:
            segmentLen = timecodeIndicies[i+1] - timecodeIndicies[i]
        sourceTimecodeIn, sourceTimecodeOut = inputTxtLines[index].strip().split(' - ')
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        captionBlock = ''
        for j in range(1,segmentLen - 1):
            if j == segmentLen - 1 - 1:
                captionBlock += inputTxtLines[index+j].strip()
            else:
                captionBlock += inputTxtLines[index+j]
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionBlock + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def prSplitCsv(inputTxtLines,offsetFrames,languageCount,languageIndex,framerate,dropFrame):
    outputCsvLines = []
    for i in range(0,len(inputTxtLines), 2 + languageCount):
        sourceTimecodeIn, sourceTimecodeOut = inputTxtLines[i].strip().split(' - ')
        captionText = inputTxtLines[i + 1 + languageIndex].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,framerate,dropFrame)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,framerate,dropFrame)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('output_file', nargs = '?', default = None)
    parser.add_argument('-if', '--inputformat', choices=['avid', 'csv', 'pr', 'srt'])
    parser.add_argument('-of', '--outputformat', choices=['avid', 'csv', 'pr', 'srt'])
    parser.add_argument('-s', '--splitsingle', type = int)
    parser.add_argument('-m', '--splitmulti', type = int)
    parser.add_argument('-r', '--framerate', type = float, default = 25)
    parser.add_argument('-f', '--fromtimecode', default = '00:00:00:00')
    parser.add_argument('-t', '--totimecode', default = '00:00:00:00')
    parser.add_argument('-df', '--dropframe', action = 'store_const', const=True)
    parser.add_argument('-D', '--decoder', default = 'utf-8-sig')
    args = parser.parse_args()

    if args.outputformat == None and args.output_file == None:
        print('Please specify either an output file name or the output file format.')
        sys.exit()

    operationMode = []
    outputFileSet = 0
    explicitMode = 1
    decoder = args.decoder
    inputFileType = ''
    splitCount = 1
    sofString = '----------------Start of File----------------'
    eofString = '----------------End of File----------------'

    originTC = args.fromtimecode
    targetTC = args.totimecode
    framerate = args.framerate
    if args.dropframe == None:
        if framerate in [29.97, 59.94]:
            while True:
                dropFrameInput = input('Use drop-frame timecode (y/n, default n)): \n').strip().lower() or 'n'
                if dropFrameInput == 'y':
                    dropFrame = True
                    break
                elif dropFrameInput == 'n':
                    dropFrame = False
                    break
        else:
            dropFrame = False
    else:
        dropFrame = args.dropframe

    offsetFrames = timecodeToFrames(targetTC,framerate,dropFrame) - timecodeToFrames(originTC,framerate,dropFrame)
    srtOffsetFrames = 0 - timecodeToFrames(originTC,framerate,dropFrame)

    inputFile = args.input_file
    try:
        inputBaseDirPair = os.path.splitext(inputFile)
    except os.error as err:
        print(str(err))
        sys.exit(2)
    try:
        o = open(inputFile, 'r', encoding = args.decoder)
    except FileNotFoundError:
        print('Input file not found!')
        sys.exit(2)
    else:
        with o as readFile:
            inputLines = readFile.readlines()

    if inputBaseDirPair[1] == '.txt':
        if args.inputformat == None:
            print('Please define the type of the input txt file with [-if|--inputformat] argument\n',
                'Supported types are avid, csv, pr and srt')
            sys.exit()
        else:
            inputFileType = args.inputformat
    elif inputBaseDirPair[1] == '.csv':
        inputFileType = 'csv'
    elif inputBaseDirPair[1] == '.srt':
        inputFileType = 'srt'
    else:
        print('Input file format not supported\n Supported formats are csv, srt and txt')
        sys.exit()

#Define output file name
    if not args.output_file == None:
        try:
            outputBaseDirPair = os.path.splitext(args.output_file)
        except os.error as err:
            print(str(err))
            sys.exit(2)
        if originTC == targetTC:
            outputBaseName = outputBaseDirPair[0]
        else:
            outputBaseName = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                            + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                            + str(framerate) + 'FPS')
    else:
        if originTC == targetTC:
            outputBaseName = inputBaseDirPair[0]
        else:
            if re.match(r'.*_alignedTo_\d\d-\d\d-\d\d-\d\d_', inputBaseDirPair[0]):
                outputBaseName = (re.split(r'_alignedTo_', inputBaseDirPair[0], 1) + '_alignedTo_'
                                + targetTC[0:2] + '-' + targetTC[3:5] + '-' + targetTC[6:8] + '-'
                                + targetTC[9:11] + '_' + str(framerate) + 'FPS')
            else:
                outputBaseName = (inputBaseDirPair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                + str(framerate) + 'FPS')

#Define output file extention
    if (not args.outputformat == None):
        outputFileType = args.outputformat
    else:
        if outputBaseDirPair[1] == '.txt' or outputBaseDirPair[1] == '':
            print('Please define the type of the output txt file with [-of|--outformat] argument\n',
                'Supported types are avid, csv, pr and srt')
            sys.exit()
        elif outputBaseDirPair[1] == '.csv':
            outputFileType = 'csv'
        elif outputBaseDirPair[1] == '.srt':
            outputFileType = 'srt'
        else:
            print("Defined output file extension not supported")

    if (not args.splitsingle == None) and args.splitsingle >= 2:
        print('WIP')
    elif (not args.splitmulti == None) and args.splitmulti >= 2:
        splitCount = args.splitmulti
        if outputFileType == 'avid':
            if inputFileType == 'avid':
                print('WIP')
            elif inputFileType == 'csv':
                print('WIP')
            elif inputFileType == 'pr':
                print('WIP')
            elif inputFileType == 'srt':
                print('WIP')
        elif outputFileType == 'csv':
            if inputFileType == 'avid':
                print('WIP')
            elif inputFileType == 'csv':
                print('WIP')
            elif inputFileType == 'pr':
                for l in range(splitCount):
                    outputFile = outputBaseName + '_L' + str(l+1) + '.csv'
                    print(f'\n\n\nWriting L{l + 1} of Pr Subtitles as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = prSplitCsv(inputLines,offsetFrames,splitCount,l,framerate,dropFrame)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
            elif inputFileType == 'srt':
                for l in range(splitCount):
                    outputFile = outputBaseName + '_L' + str(l+1) + '.csv'
                    print(f'\n\n\nWriting L{l + 1} of SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = srtSplitCsv(inputLines,offsetFrames,framerate,splitCount,l)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
        elif outputFileType == 'srt':
            if inputFileType == 'avid':
                print('WIP')
            elif inputFileType == 'csv':
                print('WIP')
            elif inputFileType == 'pr':
                print('WIP')
            elif inputFileType == 'srt':
                print('WIP')
    else:
        if outputFileType == 'avid':
            outputFile = outputBaseName + '.txt'
            if inputFileType == 'avid':
                print(f'\n\n\nWriting Avid Media Composer Subcap to {outputFile}\n\n{sofString}')
                outputSubcapLines = amcAlign(inputLines,offsetFrames,framerate,dropFrame)
                with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                    outputSubcap.writelines(outputSubcapLines)
                print(eofString)
            elif inputFileType == 'csv':
                print(f'\n\n\nConverting from CSV to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                outputSubcapLines = csvToAmc(inputLines,offsetFrames,framerate,dropFrame)
                with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                    outputSubcap.writelines(outputSubcapLines)
                print(eofString)
            elif inputFileType == 'pr':
                print('WIP')
            elif inputFileType == 'srt':
                print(f'\n\n\nConverting from SRT to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                outputSubcapLines = srtToAmc(inputLines,offsetFrames,framerate)
                with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                    outputSubcap.writelines(outputSubcapLines)
                print(eofString)
        elif outputFileType == 'csv':
            outputFile = outputBaseName + '.csv'
            if inputFileType == 'avid':
                print(f'\n\n\nWriting Avid Media Composer Subcap as CSV to {outputFile}\n\n{sofString}')
                outputCsvLines = amcToCsv(inputLines,offsetFrames,framerate,dropFrame)
                with open(outputFile, 'w', encoding=decoder) as outputCsv:
                    outputCsv.writelines(outputCsvLines)
                print(eofString)
            elif inputFileType == 'csv':
                print(f'\n\n\nWriting aligned CSV to: {outputFile}\n\n{sofString}')
                outputCsvLines = csvAlign(inputLines,offsetFrames,framerate,dropFrame)
                with open(outputFile, 'w', encoding=decoder) as outputCsv:
                    outputCsv.writelines(outputCsvLines)
                print(eofString)
            elif inputFileType == 'pr':
                print(f'\n\n\nWriting Premiere Pro subtitles as CSV to: {outputFile}\n\n{sofString}')
                outputCsvLines = prToCsv(inputLines,offsetFrames,framerate,dropFrame)
                with open(outputFile, 'w', encoding=decoder) as outputCsv:
                    outputCsv.writelines(outputCsvLines)
                print(eofString)
            elif inputFileType == 'srt':
                print(f'\n\n\nWriting SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                outputCsvLines = srtToCsv(inputLines,offsetFrames,framerate)
                with open(outputFile, 'w', encoding=decoder) as outputCsv:
                    outputCsv.writelines(outputCsvLines)
                print(eofString)
        elif outputFileType == 'srt':
            ouputFile = outputBaseName + '.srt'
            if inputFileType == 'avid':
                print(f'\n\n\nConverting from Avid Media Composer Subcap to SRT: {outputFile}\n\n{sofString}')
                outputSrtLines = amcToSrt(inputLines,srtOffsetFrames,framerate)
                with open(outputFile, 'w', encoding=decoder) as outputSrt:
                    outputSrt.writelines(outputSrtLines)
                print(eofString)
            elif inputFileType == 'csv':
                print(f'\n\n\nConverting from CSV to SRT: {outputFile}\n\n{sofString}')
                outputSrtLines = csvToSrt(inputLines,srtOffsetFrames,framerate)
                with open(outputFile, 'w', encoding=decoder) as outputSrt:
                    outputSrt.writelines(outputSrtLines)
                print(eofString)
            elif inputFileType == 'pr':
                print('WIP')
            elif inputFileType == 'srt':
                print('WIP')
        elif outputFileType == 'pr':
            print('WIP')
