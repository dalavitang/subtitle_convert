import getopt, sys, os, re

def timecodeToFrames(tcString,frameRate,dropFrame='n'):
    tcString = tcString.strip()
    tcHH, tcMM, tcSS, tcFF = int(tcString[0:2]), int(tcString[3:5]), int(tcString[6:8]), int(tcString[9:11])
    timeBase = round(float(frameRate))
    if dropFrame == 'n':
        frameNumber = tcFF + (((tcHH * 60 + tcMM) * 60) + tcSS) * timeBase
    else:
        totalMinutes = tcHH * 60 + tcMM
        framesDropped = round(frameRate * 2 / 30)
        frameNumber = (totalMinutes * 60 + tcSS) * timeBase + tcFF - (framesDropped * (totalMinutes - totalMinutes // 10))
    return frameNumber

def timecodeToSrtTimestamp(tcString,frameRate):
    tcHH, tcMM, tcSS, tcFF = tcString.split(':')
    srtMS = str(int(int(tcFF)/frameRate*1000)).zfill(3)
    srtTimestamp = tcHH + ':' + tcMM + ':' + tcSS + ',' + srtMS
    return srtTimestamp

def srtTimestampToTimecode(srtTimestamp,frameRate):
    tcHH, tcMM, srtSSMS = srtTimestamp.split(':')
    tcSS, srtMS = srtSSMS.split(',')
    tcFF = int(int(srtMS) / 1000 * frameRate)
    tcString = tcHH + ':' + tcMM + ':' + tcSS + ':' + str(tcFF).zfill(2)
    return tcString

def framesToTimecode(frameNumber,frameRate,dropFrame='n'):
    timeBase = round(float(frameRate))
    if dropFrame == 'n':
        tcFF = int(frameNumber % timeBase)
        totalSeconds = frameNumber // timeBase
        tcHH = int(totalSeconds // 3600)
        tcMM = int((totalSeconds - tcHH * 3600) // 60)
        tcSS = int(totalSeconds % 60)
        tcString = str(tcHH).zfill(2) + ':' + str(tcMM).zfill(2) + ':' + str(tcSS).zfill(2) + ':' + str(tcFF).zfill(2)
    else:
        framesDropped = round(frameRate * 2 / 30)
        framesPerHour = round(frameRate * 3600)
        framesTenMinutes = round(frameRate * 600)
        framesPerMinute = round(frameRate) * 60 - framesDropped
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

def timecodeAlign(sourceTimecode,framesDiff,frameRate):
    targetFramesCount = timecodeToFrames(sourceTimecode,frameRate) + framesDiff
    return framesToTimecode(targetFramesCount,frameRate)

def amcAlignAmc(inputSubcapLines,offsetFrames,frameRate):
    outputSubcapLines = []
    for inputLine in inputSubcapLines:
        if re.match(r'^\d\d:\d\d:\d\d:\d\d\s\d\d:\d\d:\d\d:\d\d',inputLine):
            sourceTimecodeIn, sourceTimecodeOut = inputLine.split()
            timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
            timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
            outputLine = timecodeIn + ' ' + timecodeOut + '\n'
            print(outputLine,end='')
            outputSubcapLines.append(outputLine)
        else:
            outputLine = inputLine
            print(outputLine,end='')
            outputSubcapLines.append(outputLine)
    return outputSubcapLines

def amcConvertSrt(inputSubcapLines,srtOffsetFrames,frameRate):
    outputSrtLines = []
    for i in range(3,len(inputSubcapLines)-2,3):
        index = int(i // 3)
        sourceTimecode = inputSubcapLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut = sourceTimecode.split()
        captionText = inputSubcapLines[i+1].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,srtOffsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,srtOffsetFrames,frameRate)
        timecodeInSrt = timecodeToSrtTimestamp(timecodeIn,frameRate)
        timecodeOutSrt = timecodeToSrtTimestamp(timecodeOut,frameRate)
        timecodeSrt = timecodeInSrt + ' --> ' + timecodeOutSrt
        print(f'{str(index)}\n{timecodeSrt}\n{captionText}\n')
        outputSrtLines.append(f'{str(index)}\n')
        outputSrtLines.append(f'{timecodeSrt}\n')
        outputSrtLines.append(f'{captionText}\n')
        outputSrtLines.append(f'\n')
    return outputSrtLines

def amcExportCsv(inputSubcapLines,offsetFrames,frameRate):
    outputCsvLines = []
    for i in range(3,len(inputSubcapLines)-2,3):
        sourceTimecode = inputSubcapLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut = sourceTimecode.split()
        captionText = inputSubcapLines[i+1].strip()
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def csvAlignCsv(inputCsvLines,offsetFrames,frameRate):
    outputCsvLines = []
    for i in range(0,len(inputCsvLines)):
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        captionText = captionText.strip('"')
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

def csvConvertSrt(inputCsvLines,srtOffsetFrames,frameRate):
    outputSrtLines = []
    for i in range(0,len(inputCsvLines)):
        index = i + 1
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        timecodeIn = timecodeAlign(sourceTimecodeIn,srtOffsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,srtOffsetFrames,frameRate)
        timecodeInSrt = timecodeToSrtTimestamp(timecodeIn,frameRate)
        timecodeOutSrt = timecodeToSrtTimestamp(timecodeOut,frameRate)
        timecodeSrt = timecodeInSrt + ' --> ' + timecodeOutSrt
        captionText = captionText.strip('"')
        print(f'{str(index)}\n{timecodeSrt}\n{captionText}\n')
        outputSrtLines.append(f'{str(index)}\n')
        outputSrtLines.append(f'{timecodeSrt}\n')
        outputSrtLines.append(f'{captionText}\n')
        outputSrtLines.append(f'\n')
    return outputSrtLines

def csvExportAmc(inputCsvLines,offsetFrames,frameRate):
    outputSubcapLines = []
    amcStart = '@ This file written with the Avid Caption plugin, version 1\n\n<begin subtitles>\n'
    amcEnd = '<end subtitles>\n'
    print(amcStart,end='')
    outputSubcapLines.append(amcStart)
    for i in range(0,len(inputCsvLines)):
        inputLine = inputCsvLines[i].strip()
        sourceTimecodeIn, sourceTimecodeOut, captionText = inputLine.split(',',2)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        captionText = captionText.strip('"')
        tcString = timecodeIn + ' ' + timecodeOut
        print(f'{tcString}\n{captionText}\n')
        outputSubcapLines.append(f'{tcString}\n')
        outputSubcapLines.append(f'{captionText}\n')
        outputSubcapLines.append(f'\n')
    print(amcEnd,end='')
    outputSubcapLines.append(amcEnd)
    return outputSubcapLines

def srtConvertAmc(inputSrtLines,offsetFrames,frameRate):
    outputSubcapLines = []
    amcStart = '@ This file written with the Avid Caption plugin, version 1\n\n<begin subtitles>\n'
    amcEnd = '<end subtitles>\n'
    print(amcStart,end='')
    outputSubcapLines.append(amcStart)
    for i in range(0, len(inputSrtLines), 4):
        srtTimestampIn, srtTimestampOut = inputSrtLines[i + 1].strip().split(' --> ')
        captionText = inputSrtLines[i + 2].strip()
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,frameRate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,frameRate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        tcString = timecodeIn + ' ' + timecodeOut
        print(f'{tcString}\n{captionText}\n')
        outputSubcapLines.append(f'{tcString}\n')
        outputSubcapLines.append(f'{captionText}\n')
        outputSubcapLines.append(f'\n')
    print(amcEnd,end='')
    outputSubcapLines.append(amcEnd)
    return outputSubcapLines

def srtDumpCsv(inputSrtLines,offsetFrames,frameRate):
    outputCsvLines = []
    i = 0
    n = len(inputSrtLines)
    while i < n:
        try:
            currentIndex = int(inputSrtLines[i].strip())
        except:
            i += 1
            continue
        try:
            j = inputSrtLines.index(f'{currentIndex + 1}\n')
        except ValueError as vErr:
            j = n
        srtTimestampIn, srtTimestampOut = inputSrtLines[i + 1].strip().split(' --> ')
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,frameRate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,frameRate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        captionBlock = ''
        for k in range(i + 2, j):
            if k == j - 2:
                captionText = inputSrtLines[k].strip()
            else:
                captionText = inputSrtLines[k]
            if captionText.strip() == '':
                pass
            else:
                captionBlock += captionText            
        if captionBlock == '':
            i = j
        else:
            outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionBlock + '"\n'
            print(outputLine,end='')
            outputCsvLines.append(outputLine)
            i = j
    return outputCsvLines

def srtSplitCsv(inputSrtLines,offsetFrames,frameRate,languageCount,languageIndex):
    outputCsvLines = []
    for i in range(0, len(inputSrtLines), 3 + languageCount):
        srtTimestampIn, srtTimestampOut = inputSrtLines[i + 1].strip().split(' --> ')
        captionText = inputSrtLines[i + 2 + languageIndex].strip()
        sourceTimecodeIn = srtTimestampToTimecode(srtTimestampIn,frameRate)
        sourceTimecodeOut = srtTimestampToTimecode(srtTimestampOut,frameRate)
        timecodeIn = timecodeAlign(sourceTimecodeIn,offsetFrames,frameRate)
        timecodeOut = timecodeAlign(sourceTimecodeOut,offsetFrames,frameRate)
        outputLine = timecodeIn + ',' + timecodeOut + ',' + '"' + captionText + '"\n'
        print(outputLine,end='')
        outputCsvLines.append(outputLine)
    return outputCsvLines

if __name__ == '__main__':
    argvList = sys.argv[1:]
    optList = 'haces:D:i:o:'
    loptList = ['help', 'align', 'convert', 'export', 'split=', 'decoder=', 'input=', 'output=']
    operationMode = []
    outputFileSet = 0
    explicitMode = 1
    decoder = 'utf-8-sig'
    splitCount = 1
    sofString = '----------------Start of File----------------'
    eofString = '----------------End of File----------------'
    helpMsg = ('Usage: amc_subcap.py [-a|--align] [-c|--convert] [-e|--export] [-s|--split <split_count>] [-D|--decoder <decoder>] [-i|--input <inputfile>] [-o|--output <outputfile>]\n\n'
               + 'For Avid Media Composer Subcap files:\n'
               + '\t-a or --align options align the timecode from source to target and writes to a new Subcap file\n'
               + '\t-c or --convert options convert the Subcap file to an SRT file with starting time aligned to 00:00:00,000\n'
               + '\t-e or --export options export the Subcap file to a csv file for easy process\n\n'
               + 'For SRT files:\n'
               + '\t-a, --align, -c or --convert options align the timecode to target and writes to a new Subcap file\n'
               + '\t-s or --split options seperate the output file into split_count number of languages\n'
               + '\t-e or --export options convert the SRT file to a csv file with timecode aligned to target and formated as HH:MM:SS:FF\n'
               + '\tNote that for SRT files, source timecode is always 00:00:00,000\n\n'
               + 'For Comma Seperated Values(CSV) files:\n'
               + '\t-a or --align options align the timecode from source to target and writes to a new CSV file\n'
               + '\t-c or --convert options convert the Subcap file to an SRT file with starting time aligned to 00:00:00,000\n'
               + '\t-e or --export options export the CSV file to an Avid Media Composer Subcap file\n\n'
               + 'If output file is provided, operation mode will be inferred from the output file extension\n'
               + 'If any operation mode is set, output file extension will be disregarded\n\n'
               + 'Default decoder is UTF-8-SIG')
    
    if len(argvList) == 0:
        print(helpMsg)
        sys.exit(0)
    
    try:
        argv, values = getopt.getopt(argvList, optList, loptList)
    except getopt.error as err:
        print(str(err))
        print(helpMsg)
        sys.exit(2)
        
    for currentArgv, currentValue in argv:
        if currentArgv in ('-h', '--help'):
            print(helpMsg)
            sys.exit(0)
        elif currentArgv in ('-a', '--align'):
            operationMode.append('align')
        elif currentArgv in ('-c', '--convert'):
            operationMode.append('convert')
        elif currentArgv in ('-e', '--export'):
            operationMode.append('export')
        elif currentArgv in ('-s', '--split'):
            operationMode.append('split')
            splitCount = int(currentValue)
        elif currentArgv in ('-D', '--decoder'):
            decoder = currentValue
        elif currentArgv in ('-i', '--input'):
            inputFile = currentValue
            try:
                inputBaseDirPair = os.path.splitext(inputFile)
            except os.error as err:
                print(str(err))
                sys.exit(2)
        elif currentArgv in ('-o', '--output'):
            outputFile = currentValue
            try:
                outputBaseDirPair = os.path.splitext(outputFile)
            except os.error as err:
                print(str(err))
                sys.exit(2)
            outputFileSet = 1

    if len(operationMode) == 0:
        explicitMode = 0
        if outputFileSet == 0:
            print(f'Please provide at least one operation mode or an output file name')
            print(helpMsg)
            sys.exit(2)
        else:
            if inputBaseDirPair[1] == '.txt':
                if outputBaseDirPair[1] == '.txt':
                    operationMode.append('align')
                elif outputBaseDirPair[1] == '.srt':
                    operationMode.append('convert')
                elif outputBaseDirPair[1] == '.csv':
                    operationMode.append('export')
                else:
                    print(f'Output file extension not supported!')
                    sys.exit(0)
            elif inputBaseDirPair[1] == '.srt':
                if outputBaseDirPair[1] == '.txt':
                    operationMode.append('convert')
                elif outputBaseDirPair[1] == '.srt':
                    print(f'Operation mode not supported!')
                    sys.exit(0)
                elif outputBaseDirPair[1] == '.csv':
                    operationMode.append('export')
                else:
                    print(f'Output file extension not supported!')
                    sys.exit(0)
            elif inputBaseDirPair[1] == '.csv':
                if outputBaseDirPair[1] == '.txt':
                    operationMode.append('export')
                elif outputBaseDirPair[1] == '.srt':
                    operationMode.append('convert')
                elif outputBaseDirPair[1] == '.csv':
                    operationMode.append('align')
                else:
                    print(f'Output file extension not supported!')
                    sys.exit(0)
            else:
                print('Input file format not supported!')
                sys.exit(0)
    elif len(operationMode) == 1:
        if outputFileSet == 0:
            pass
        else:
            print(f'Operation mode explicitly set, output file extension will not be respected.')
    else: 
        if outputFileSet == 0:
            pass
        else:
            print(f'More than one operation mode set, output file extention will not be respected.')
    
    originTC = input('Please enter origin timecode (00:00:00:00): \n').strip() or '00:00:00:00'
    targetTC = input(f'Please enter target timecode ({originTC}): \n').strip() or originTC
    frameRateStr = input('Please enter project frame rate (25): \n').strip() or '25'
    if frameRateStr in ['29.97', '59.94']:
        while True:
            dropFrameInput = input('Use drop-frame timecode (y/n, default n)): \n').strip().lower() or 'n'
            if dropFrameInput in ['y', 'n']:
                dropFrame = dropFrameInput
                break
    else:
        dropFrame = 'n'
    frameRate = float(frameRateStr)
    offsetFrames = timecodeToFrames(targetTC,frameRate) - timecodeToFrames(originTC,frameRate)
    srtOffsetFrames = 0 - timecodeToFrames(originTC,frameRate)
    if explicitMode == 1:
        if inputBaseDirPair[1] == '.txt':
            with open(inputFile, 'r', encoding=decoder) as inputSubcap:
                inputSubcapLines = inputSubcap.readlines()
            if re.match(r'.*_alignedTo_\d\d-\d\d-\d\d-\d\d_\d+FPS', inputBaseDirPair[0]):
                outputBaseNamePair = re.split(r'_alignedTo_', inputBaseDirPair[0], 1)
            else:
                outputBaseNamePair = inputBaseDirPair
            for mode in operationMode:
                if mode == 'align':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + inputBaseDirPair[1])
                    else:
                        outputFile = (outputBaseDirPair[0] + inputBaseDirPair[1])
                    print(f'\n\n\nWriting Avid Media Composer Subcap to {outputFile}\n\n{sofString}')
                    outputSubcapLines = amcAlignAmc(inputSubcapLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
                elif mode == 'export':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.csv')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.csv')
                    print(f'\n\n\nWriting Avid Media Composer Subcap as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = amcExportCsv(inputSubcapLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'convert':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.srt')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.srt')
                    print(f'\n\n\nConverting from Avid Media Composer Subcap to SRT: {outputFile}\n\n{sofString}')
                    outputSrtLines = amcConvertSrt(inputSubcapLines,srtOffsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSrt:
                        outputSrt.writelines(outputSrtLines)
                    print(eofString)
        elif inputBaseDirPair[1] == '.srt':
            with open(inputFile, 'r', encoding=decoder) as inputSrt:
                inputSrtLines = inputSrt.readlines()
            if re.match(r'.*_alignedTo_\d\d-\d\d-\d\d-\d\d_\d+FPS', inputBaseDirPair[0]):
                outputBaseNamePair = re.split(r'_alignedTo_', inputBaseDirPair[0], 1)
            else:
                outputBaseNamePair = inputBaseDirPair
            for mode in operationMode:
                if mode in ('convert', 'align'):
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.txt')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.txt')
                    print(f'\n\n\nConverting from SRT to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                    outputSubcapLines = srtConvertAmc(inputSrtLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
                elif mode == 'export':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.csv')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.csv')
                    print(f'\n\n\nWriting SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = srtDumpCsv(inputSrtLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'split':
                    if splitCount == 0:
                        print('Split count set to 0, switching to Export operation')
                        if outputFileSet == 0:
                            outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                        + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                        + str(frameRate) + 'FPS' + '.csv')
                        else:
                            outputFile = (outputBaseDirPair[0] + '.csv')
                        print(f'\n\n\nWriting SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                        outputCsvLines = srtDumpCsv(inputSrtLines,offsetFrames,frameRate)
                        with open(outputFile, 'w', encoding=decoder) as outputCsv:
                            outputCsv.writelines(outputCsvLines)
                        print(eofString)
                    else:
                        for l in range(splitCount):
                            if outputFileSet == 0:
                                outputFile = (outputBaseNamePair[0] + 'L' + str(l+1) + '_alignedTo_'
                                            + targetTC[0:2] + '-' + targetTC[3:5] + '-' + targetTC[6:8] + '-' + targetTC[9:11]
                                            + '_' + str(frameRate) + 'FPS' + '.csv')
                            else:
                                outputFile = (outputBaseDirPair[0] + 'L' + str(l+1) + '.csv')
                            print(f'\n\n\nWriting L{l + 1} of SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                            outputCsvLines = srtSplitCsv(inputSrtLines,offsetFrames,frameRate,splitCount,l)
                            with open(outputFile, 'w', encoding=decoder) as outputCsv:
                                outputCsv.writelines(outputCsvLines)
                            print(eofString)
        elif inputBaseDirPair[1] == '.csv':
            with open(inputFile, 'r', encoding=decoder) as inputCsv:
                inputCsvLines = inputCsv.readlines()
            if re.match(r'.*_alignedTo_\d\d-\d\d-\d\d-\d\d_\d+FPS', inputBaseDirPair[0]):
                outputBaseNamePair = re.split(r'_alignedTo_', inputBaseDirPair[0], 1)
            else:
                outputBaseNamePair = inputBaseDirPair
            for mode in operationMode:
                if mode == 'align':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + inputBaseDirPair[1])
                    else:
                        outputFile = (outputBaseDirPair[0] + inputBaseDirPair[1])
                    print(f'\n\n\nWriting aligned CSV to: {outputFile}\n\n{sofString}')
                    outputCsvLines = csvAlignCsv(inputCsvLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'convert':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.srt')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.srt')
                    print(f'\n\n\nConverting from CSV to SRT: {outputFile}\n\n{sofString}')
                    outputSrtLines = csvConvertSrt(inputCsvLines,srtOffsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSrt:
                        outputSrt.writelines(outputSrtLines)
                    print(eofString)
                elif mode == 'export':
                    if outputFileSet == 0:
                        outputFile = (outputBaseNamePair[0] + '_alignedTo_' + targetTC[0:2] + '-' + targetTC[3:5]
                                    + '-' + targetTC[6:8] + '-' + targetTC[9:11] + '_'
                                    + str(frameRate) + 'FPS' + '.txt')
                    else:
                        outputFile = (outputBaseDirPair[0] + '.txt')
                    print(f'\n\n\nConverting from CSV to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                    outputSubcapLines = csvExportAmc(inputCsvLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
        else:
            print('Input file format not supported!')
            sys.exit(0)
    else:
        if inputBaseDirPair[1] == '.txt':
            with open(inputFile, 'r', encoding=decoder) as inputSubcap:
                inputSubcapLines = inputSubcap.readlines()
            for mode in operationMode:
                if mode == 'align':
                    outputFile = (outputBaseDirPair[0] + inputBaseDirPair[1])
                    print(f'\n\n\nWriting Avid Media Composer Subcap to {outputFile}\n\n{sofString}')
                    outputSubcapLines = amcAlignAmc(inputSubcapLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
                elif mode == 'export':
                    outputFile = (outputBaseDirPair[0] + '.csv')
                    print(f'\n\n\nWriting Avid Media Composer Subcap as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = amcExportCsv(inputSubcapLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'convert':
                    outputFile = (outputBaseDirPair[0] + '.srt')
                    print(f'\n\n\nConverting from Avid Media Composer Subcap to SRT: {outputFile}\n\n{sofString}')
                    outputSrtLines = amcConvertSrt(inputSubcapLines,srtOffsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSrt:
                        outputSrt.writelines(outputSrtLines)
                    print(eofString)
        elif inputBaseDirPair[1] == '.srt':
            with open(inputFile, 'r', encoding=decoder) as inputSrt:
                inputSrtLines = inputSrt.readlines()
            for mode in operationMode:
                if mode in ('convert', 'align'):
                    outputFile = (outputBaseDirPair[0] + '.txt')
                    print(f'\n\n\nConverting from SRT to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                    outputSubcapLines = srtConvertAmc(inputSrtLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
                elif mode == 'export':
                    outputFile = (outputBaseDirPair[0] + '.csv')
                    print(f'\n\n\nWriting SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                    outputCsvLines = srtDumpCsv(inputSrtLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'split':
                    if splitCount == 0:
                        print('Split count set to 0, switching to Export operation')
                        outputFile = (outputBaseDirPair[0] + '.csv')
                        print(f'\n\n\nWriting SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                        outputCsvLines = srtDumpCsv(inputSrtLines,offsetFrames,frameRate)
                        with open(outputFile, 'w', encoding=decoder) as outputCsv:
                            outputCsv.writelines(outputCsvLines)
                        print(eofString)
                    else:
                        for l in range(splitCount):
                            outputFile = (outputBaseDirPair[0] + 'L' + str(l+1) + '.csv')
                            print(f'\n\n\nWriting L{l + 1} of SRT Subtitles as CSV to {outputFile}\n\n{sofString}')
                            outputCsvLines = srtSplitCsv(inputSrtLines,offsetFrames,frameRate,splitCount,l)
                            with open(outputFile, 'w', encoding=decoder) as outputCsv:
                                outputCsv.writelines(outputCsvLines)
                            print(eofString)
        elif inputBaseDirPair[1] == '.csv':
            with open(inputFile, 'r', encoding=decoder) as inputCsv:
                inputCsvLines = inputCsv.readlines()
            for mode in operationMode:
                if mode == 'align':
                    outputFile = (outputBaseDirPair[0] + inputBaseDirPair[1])
                    print(f'\n\n\nWriting aligned CSV to: {outputFile}\n\n{sofString}')
                    outputCsvLines = csvAlignCsv(inputCsvLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputCsv:
                        outputCsv.writelines(outputCsvLines)
                    print(eofString)
                elif mode == 'convert':
                    outputFile = (outputBaseDirPair[0] + '.srt')
                    print(f'\n\n\nConverting from CSV to SRT: {outputFile}\n\n{sofString}')
                    outputSrtLines = csvConvertSrt(inputCsvLines,srtOffsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSrt:
                        outputSrt.writelines(outputSrtLines)
                    print(eofString)
                elif mode == 'export':
                    outputFile = (outputBaseDirPair[0] + '.txt')
                    print(f'\n\n\nConverting from CSV to Avid Media Composer Subcap: {outputFile}\n\n{sofString}')
                    outputSubcapLines = csvExportAmc(inputCsvLines,offsetFrames,frameRate)
                    with open(outputFile, 'w', encoding=decoder) as outputSubcap:
                        outputSubcap.writelines(outputSubcapLines)
                    print(eofString)
        else:
            print('Input file format not supported!')
            sys.exit(0)
