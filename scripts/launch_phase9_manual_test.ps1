[CmdletBinding()]
param(
    [switch]$Worker,
    [string]$RunDirectory,
    [string]$RunName,
    [string]$PersistenceSourceRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repoRoot = Split-Path -Parent $PSScriptRoot
$executable = Join-Path $repoRoot 'build-phase8-private\Release\jfg-native-boot.exe'
$romPath = Join-Path $repoRoot 'tools\upstream\Jet-Force-Gemini\build\jfg.us.z64'
$savePath = Join-Path $repoRoot 'build-phase8-private\phase9-persistence.flash'
$pakPath = Join-Path $repoRoot 'build-phase8-private\phase9-persistence.pak'
$taskName = 'JFG Phase9 Manual Test'

if (-not $Worker -and -not [string]::IsNullOrWhiteSpace($PersistenceSourceRun)) {
    $savePath = Join-Path $PersistenceSourceRun 'initial.flash'
    $pakPath = Join-Path $PersistenceSourceRun 'initial.pak'
}

function Assert-RequiredFile([string]$Path, [string]$Description) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description was not found: $Path"
    }
}

function Write-WatchdogEvent([string]$Message) {
    $line = "{0}`t{1}" -f (Get-Date).ToString('o'), $Message
    Add-Content -LiteralPath (Join-Path $RunDirectory 'watchdog.log') -Value $line -Encoding UTF8
}

Assert-RequiredFile $executable 'Native runtime executable'
Assert-RequiredFile $romPath 'Recompiled ROM'
Assert-RequiredFile $savePath 'Phase 9 Flash save'
Assert-RequiredFile $pakPath 'Phase 9 controller pak'

if ($Worker) {
    if ([string]::IsNullOrWhiteSpace($RunDirectory) -or
        -not (Test-Path -LiteralPath $RunDirectory -PathType Container)) {
        throw "Worker run directory was not found: $RunDirectory"
    }

    $progressPath = Join-Path $RunDirectory 'progress.json'
    $inputPath = Join-Path $RunDirectory 'controller.input'
    $stdoutPath = Join-Path $RunDirectory 'stdout.log'
    $stderrPath = Join-Path $RunDirectory 'stderr.log'
    $statusPath = Join-Path $RunDirectory 'status.json'
    $pidPath = Join-Path $RunDirectory 'game.pid'
    $startedAt = Get-Date

    # The launcher snapshots persistence before registering the worker. Keep
    # the live run isolated from the shared Phase 9 save so replay can always
    # start from byte-identical menu/save state.
    $workingSave = Join-Path $RunDirectory 'working.flash'
    $workingPak = Join-Path $RunDirectory 'working.pak'
    Assert-RequiredFile $workingSave 'Run-local Flash image'
    Assert-RequiredFile $workingPak 'Run-local controller pak'
    $savePath = $workingSave
    $pakPath = $workingPak

    $env:JFG_PHASE8_PROGRESS = $progressPath
    $env:JFG_PHASE9_INPUT_RECORD = $inputPath
    Remove-Item Env:JFG_PHASE8_INPUT_REPLAY, Env:JFG_PHASE9_FAST_REPLAY -ErrorAction SilentlyContinue

    $arguments = '--rom "{0}" --save "{1}" --controller-pak "{2}" --play' -f `
        $romPath, $savePath, $pakPath

    Write-WatchdogEvent 'launching game'
    try {
        $process = Start-Process -FilePath $executable `
            -ArgumentList $arguments `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru
        Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ASCII
        Write-WatchdogEvent ("game started pid={0}" -f $process.Id)

        while (-not $process.HasExited) {
            $process.Refresh()
            [ordered]@{
                state = 'running'
                pid = $process.Id
                started_at = $startedAt.ToString('o')
                heartbeat_at = (Get-Date).ToString('o')
                progress_path = $progressPath
                input_path = $inputPath
                stdout_path = $stdoutPath
                stderr_path = $stderrPath
            } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
            Start-Sleep -Seconds 2
        }
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $endedAt = Get-Date
        [ordered]@{
            state = 'exited'
            pid = $process.Id
            exit_code = $exitCode
            started_at = $startedAt.ToString('o')
            ended_at = $endedAt.ToString('o')
            duration_seconds = [math]::Round(($endedAt - $startedAt).TotalSeconds, 3)
            progress_path = $progressPath
            input_path = $inputPath
            stdout_path = $stdoutPath
            stderr_path = $stderrPath
        } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
        Write-WatchdogEvent ("game exited code={0}" -f $exitCode)
        exit $exitCode
    }
    finally {
        # The launcher pointed the machine-wide LocalDumps key for this
        # executable at the run directory and registered this task. Neither
        # may outlive the run: the next run re-creates both, and a stale key
        # would route unrelated crash dumps into an old directory.
        $dumpKey = 'HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\jfg-native-boot.exe'
        Remove-Item -Path $dumpKey -Recurse -Force -ErrorAction SilentlyContinue
        Write-WatchdogEvent 'removed crash dump registry key'
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    catch {
        [ordered]@{
            state = 'watchdog-error'
            started_at = $startedAt.ToString('o')
            ended_at = (Get-Date).ToString('o')
            error = $_.Exception.Message
        } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
        Write-WatchdogEvent ("watchdog error: {0}" -f $_.Exception.Message)
        throw
    }
}

if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = 'manual-stutter-{0}' -f (Get-Date -Format 'yyyyMMdd-HHmmss')
}
if ($RunName -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') {
    throw 'RunName must contain only letters, numbers, dots, underscores, or hyphens.'
}

$manualRoot = Join-Path $repoRoot 'build-phase8-private\manual-tests'
$RunDirectory = Join-Path $manualRoot $RunName
if (Test-Path -LiteralPath $RunDirectory) {
    throw "Run directory already exists: $RunDirectory"
}
New-Item -ItemType Directory -Path $RunDirectory -Force | Out-Null
$dumpDirectory = Join-Path $RunDirectory 'crash-dumps'
New-Item -ItemType Directory -Path $dumpDirectory -Force | Out-Null
$initialSave = Join-Path $RunDirectory 'initial.flash'
$initialPak = Join-Path $RunDirectory 'initial.pak'
$workingSave = Join-Path $RunDirectory 'working.flash'
$workingPak = Join-Path $RunDirectory 'working.pak'
[System.IO.File]::Copy($savePath, $initialSave, $false)
[System.IO.File]::Copy($pakPath, $initialPak, $false)
[System.IO.File]::Copy($initialSave, $workingSave, $false)
[System.IO.File]::Copy($initialPak, $workingPak, $false)

$dumpKey = 'HKCU:\Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\jfg-native-boot.exe'
New-Item -Path $dumpKey -Force | Out-Null
New-ItemProperty -Path $dumpKey -Name DumpFolder -PropertyType ExpandString `
    -Value $dumpDirectory -Force | Out-Null
New-ItemProperty -Path $dumpKey -Name DumpType -PropertyType DWord -Value 2 -Force | Out-Null
New-ItemProperty -Path $dumpKey -Name DumpCount -PropertyType DWord -Value 10 -Force | Out-Null

[ordered]@{
    run_name = $RunName
    created_at = (Get-Date).ToString('o')
    executable = $executable
    rom = $romPath
    source_save = $savePath
    source_controller_pak = $pakPath
    initial_save = $initialSave
    initial_controller_pak = $initialPak
    working_save = $workingSave
    working_controller_pak = $workingPak
    dump_directory = $dumpDirectory
    task_name = $taskName
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDirectory 'manifest.json') -Encoding UTF8

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existingTask -and $existingTask.State -eq 'Running') {
    throw "The existing '$taskName' task is still running. Close that game before starting another test."
}

$workerArguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden ' +
    '-ExecutionPolicy Bypass -File "{0}" -Worker -RunDirectory "{1}"' -f `
    $PSCommandPath, $RunDirectory
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $workerArguments `
    -WorkingDirectory $repoRoot
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal `
    -Settings $settings -Description 'Isolated Jet Force Gemini Phase 9 manual test watchdog' `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

$pidPath = Join-Path $RunDirectory 'game.pid'
$deadline = (Get-Date).AddSeconds(20)
while (-not (Test-Path -LiteralPath $pidPath -PathType Leaf) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
if (-not (Test-Path -LiteralPath $pidPath -PathType Leaf)) {
    $statusPath = Join-Path $RunDirectory 'status.json'
    if (Test-Path -LiteralPath $statusPath) {
        throw "The isolated launcher failed: $(Get-Content -LiteralPath $statusPath -Raw)"
    }
    throw "The isolated launcher did not report a game process. Check $RunDirectory"
}

$gamePid = [int](Get-Content -LiteralPath $pidPath -Raw)
$gameProcess = Get-Process -Id $gamePid -ErrorAction Stop
[pscustomobject]@{
    RunDirectory = $RunDirectory
    GamePid = $gamePid
    ProcessName = $gameProcess.ProcessName
    Responding = $gameProcess.Responding
    ScheduledTask = $taskName
    CrashDumpDirectory = $dumpDirectory
}
