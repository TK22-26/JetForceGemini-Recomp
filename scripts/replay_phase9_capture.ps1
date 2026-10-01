[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRun,
    [string]$ReplayName = 'accelerated-replay',
    [ValidateRange(0, 1000000)]
    [uint64]$UntilRetrace = 0,
    [switch]$FullRender,
    [switch]$RealTime,
    [switch]$PlayMode,
    [switch]$ActorTrace,
    [switch]$RetraceHashes,
    [switch]$ReplayByPoll
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repoRoot = Split-Path -Parent $PSScriptRoot
$inputSource = Join-Path $SourceRun 'controller.input'
$executable = Join-Path $repoRoot 'build-phase8-private\Release\jfg-native-boot.exe'
$romPath = Join-Path $repoRoot 'tools\upstream\Jet-Force-Gemini\build\jfg.us.z64'
$runInitialSave = Join-Path $SourceRun 'initial.flash'
$runInitialPak = Join-Path $SourceRun 'initial.pak'
$saveSource = if (Test-Path -LiteralPath $runInitialSave -PathType Leaf) {
    $runInitialSave
} else {
    Join-Path $repoRoot 'build-phase8-private\phase9-persistence.flash'
}
$pakSource = if (Test-Path -LiteralPath $runInitialPak -PathType Leaf) {
    $runInitialPak
} else {
    Join-Path $repoRoot 'build-phase8-private\phase9-persistence.pak'
}
foreach ($required in @($inputSource, $executable, $romPath, $saveSource, $pakSource)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required replay input was not found: $required"
    }
}

$lastRecord = Get-Content -LiteralPath $inputSource -Tail 1
$fields = $lastRecord -split ','
if ($fields.Count -ne 6) {
    throw "Invalid final replay record: $lastRecord"
}
$targetRetrace = [uint64]$fields[1]
if ($targetRetrace -lt 3 -or $targetRetrace -gt 1000000) {
    throw "Replay target retrace is out of range: $targetRetrace"
}
if ($UntilRetrace -ne 0) {
    if ($UntilRetrace -lt 3 -or $UntilRetrace -gt $targetRetrace) {
        throw 'The diagnostic stop must be between retrace 3 and the recorded input end.'
    }
    $targetRetrace = $UntilRetrace
}

$replayDirectory = Join-Path $SourceRun $ReplayName
if (Test-Path -LiteralPath $replayDirectory) {
    throw "Replay directory already exists: $replayDirectory"
}
New-Item -ItemType Directory -Path $replayDirectory | Out-Null
$inputPath = Join-Path $replayDirectory 'controller.input'
$savePath = Join-Path $replayDirectory 'replay.flash'
$pakPath = Join-Path $replayDirectory 'replay.pak'
$sourceLines = [System.IO.File]::ReadAllLines($inputSource)
if ($sourceLines.Count -lt 2 -or $sourceLines[0] -ne 'jfg-phase8-input-v2') {
    throw 'The capture does not use the expected native input-v2 format.'
}
$normalizedLines = New-Object 'System.Collections.Generic.List[string]'
$normalizedLines.Add($sourceLines[0])
for ($index = 1; $index -lt $sourceLines.Count; ++$index) {
    $record = $sourceLines[$index] -split ','
    if ($record.Count -ne 6) {
        throw "Invalid replay record at line $($index + 1): $($sourceLines[$index])"
    }
    $firstRetrace = [uint64]$record[0]
    $endRetrace = [uint64]$record[1]
    if ($index + 1 -lt $sourceLines.Count) {
        $next = $sourceLines[$index + 1] -split ','
        if ($next.Count -ne 6) {
            throw "Invalid replay record at line $($index + 2): $($sourceLines[$index + 1])"
        }
        $nextRetrace = [uint64]$next[0]
        if ($nextRetrace -gt $firstRetrace) {
            $endRetrace = $nextRetrace
        }
    }
    $normalizedLines.Add(('{0},{1},{2},{3},{4},{5}' -f `
        $record[0], $endRetrace, $record[2], $record[3], $record[4], $record[5]))
}
[System.IO.File]::WriteAllLines($inputPath, $normalizedLines)
Copy-Item -LiteralPath $saveSource -Destination $savePath
Copy-Item -LiteralPath $pakSource -Destination $pakPath

$env:JFG_PHASE8_INPUT_REPLAY = $inputPath
$env:JFG_PHASE8_PROGRESS = Join-Path $replayDirectory 'progress.json'
if ($RetraceHashes) {
    $env:JFG_PHASE9_RETRACE_HASH = Join-Path $replayDirectory 'retrace-hashes.jsonl'
} else {
    Remove-Item Env:JFG_PHASE9_RETRACE_HASH -ErrorAction SilentlyContinue
}
if ($ReplayByPoll) {
    $env:JFG_PHASE9_REPLAY_BY_POLL = '1'
} else {
    Remove-Item Env:JFG_PHASE9_REPLAY_BY_POLL -ErrorAction SilentlyContinue
}
if ($ActorTrace) {
    $env:JFG_PHASE9_ACTOR_TRACE = '1'
} else {
    Remove-Item Env:JFG_PHASE9_ACTOR_TRACE -ErrorAction SilentlyContinue
}
if ($RealTime) {
    Remove-Item Env:JFG_PHASE9_FAST_REPLAY, Env:JFG_PHASE8_RDRAM_CAPTURE `
        -ErrorAction SilentlyContinue
} elseif ($FullRender) {
    $env:JFG_PHASE9_FAST_REPLAY = '1'
    # Requesting a final RDRAM capture intentionally disables the fast
    # replay graphics-skip path while retaining unpaced execution.
    $env:JFG_PHASE8_RDRAM_CAPTURE = Join-Path $replayDirectory 'final.rdram'
} else {
    $env:JFG_PHASE9_FAST_REPLAY = '1'
    Remove-Item Env:JFG_PHASE8_RDRAM_CAPTURE -ErrorAction SilentlyContinue
}
Remove-Item Env:JFG_PHASE9_INPUT_RECORD -ErrorAction SilentlyContinue

if ($PlayMode) {
    $arguments = '--rom "{0}" --save "{1}" --controller-pak "{2}" --play' -f `
        $romPath, $savePath, $pakPath
} else {
    $arguments = '--rom "{0}" --save "{1}" --controller-pak "{2}" --probe-retraces {3}' -f `
        $romPath, $savePath, $pakPath, $targetRetrace
}
$process = Start-Process -FilePath $executable -ArgumentList $arguments `
    -RedirectStandardOutput (Join-Path $replayDirectory 'stdout.log') `
    -RedirectStandardError (Join-Path $replayDirectory 'stderr.log') `
    -WindowStyle Hidden -PassThru

[pscustomobject]@{
    Pid = $process.Id
    Process = $process
    ReplayDirectory = $replayDirectory
    TargetRetrace = $targetRetrace
}
