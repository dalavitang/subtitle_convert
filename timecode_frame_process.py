def timecodeToFrames(tcString,frameRate):
    tcString = tcString.strip()
    tcHH, tcMM, tcSS, tcFF = int(tcString[0:2]), int(tcString[3:5]), int(tcString[6:8]), int(tcString[9:11])
    framesCount = tcFF + (((tcHH * 60 + tcMM) * 60) + tcSS) * frameRate
    return framesCount

def framesToTimecode(framesCount,frameRate):
    tcFF = int(framesCount % frameRate)
    totalSeconds = framesCount // frameRate
    tcHH = int(totalSeconds // 3600)
    tcMM = int((totalSeconds - tcHH * 3600) // 60)
    tcSS = int(totalSeconds % 60)
    tcString = str(tcHH).zfill(2) + ":" + str(tcMM).zfill(2) + ":" + str(tcSS).zfill(2) + ":" + str(tcFF).zfill(2)
    return tcString

def timecodeDiffInFrames(sourceTimecode,targetTimecode,frameRate):
    sourceFramesCount = timecodeToFrames(sourceTimecode,frameRate)
    targetFramesCount = timecodeToFrames(targetTimecode,frameRate)
    return targetFramesCount - sourceFramesCount

def timecodeAlign(sourceTimecode,framesDiff,frameRate):
    targetFramesCount = timecodeToFrames(sourceTimecode,frameRate) + framesDiff
    return framesToTimecode(targetFramesCount,frameRate)
