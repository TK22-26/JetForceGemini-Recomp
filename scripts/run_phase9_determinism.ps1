[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRun,
    [ValidateRange(2, 1000)]
    [int]$Runs = 100,
    [ValidateRange(1, 32)]
    [int]$Parallelism = 4,
    [string]$RunPrefix = 'determinism'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$replayScript = Join-Path $PSScriptRoot 'replay_phase9_capture.ps1'
$comparator = Join-Path $PSScriptRoot 'compare_phase9_retrace_hashes.py'
foreach ($required in @($replayScript, $comparator, $SourceRun)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required determinism input was not found: $required"
    }
}

$priorNullAudio = [Environment]::GetEnvironmentVariable(
    'JFG_PHASE9_NULL_AUDIO', 'Process')
$env:JFG_PHASE9_NULL_AUDIO = '1'
$pending = New-Object 'System.Collections.Generic.List[object]'
$completed = New-Object 'System.Collections.Generic.List[object]'
$nextRun = 1

try {
    while ($nextRun -le $Runs -or $pending.Count -gt 0) {
        while ($nextRun -le $Runs -and $pending.Count -lt $Parallelism) {
            $name = '{0}-{1:D3}' -f $RunPrefix, $nextRun
            $launch = & $replayScript -SourceRun $SourceRun `
                -ReplayName $name -RetraceHashes
            $process = $launch.Process
            if ($null -eq $process) {
                throw "Replay launcher did not return a process handle for run $nextRun"
            }
            $pending.Add([pscustomobject]@{
                Index = $nextRun
                Directory = [string]$launch.ReplayDirectory
                TargetRetrace = [uint64]$launch.TargetRetrace
                Process = $process
            })
            Write-Host "Started Phase 9 determinism run $nextRun/$Runs (PID $($launch.Pid))"
            ++$nextRun
        }

        for ($index = $pending.Count - 1; $index -ge 0; --$index) {
            $item = $pending[$index]
            if (-not $item.Process.HasExited) {
                continue
            }
            $item.Process.WaitForExit()
            $exitCode = $item.Process.ExitCode
            if ($null -ne $exitCode -and $exitCode -ne 0) {
                throw "Determinism run $($item.Index) exited ${exitCode}: $($item.Directory)"
            }
            $stdoutPath = Join-Path $item.Directory 'stdout.log'
            try {
                $result = Get-Content -LiteralPath $stdoutPath -Tail 1 |
                    ConvertFrom-Json
            } catch {
                throw "Determinism run $($item.Index) produced no valid completion record: $($item.Directory)"
            }
            if ($result.status -ne 'retrace-target' -or
                [uint64]$result.vi_retraces -ne $item.TargetRetrace -or
                [uint64]$result.unsupported_accesses -ne 0) {
                throw "Determinism run $($item.Index) did not reach a clean target: $($item.Directory)"
            }
            $hashPath = Join-Path $item.Directory 'retrace-hashes.jsonl'
            if (-not (Test-Path -LiteralPath $hashPath -PathType Leaf)) {
                throw "Determinism run $($item.Index) produced no retrace hash: $($item.Directory)"
            }
            $completed.Add([pscustomobject]@{
                Index = $item.Index
                Directory = $item.Directory
                HashPath = $hashPath
            })
            $pending.RemoveAt($index)
            Write-Host "Completed Phase 9 determinism run $($item.Index)/$Runs"
        }
        if ($pending.Count -gt 0) {
            Start-Sleep -Milliseconds 200
        }
    }
} finally {
    foreach ($item in $pending) {
        if (-not $item.Process.HasExited) {
            Stop-Process -Id $item.Process.Id -Force -ErrorAction SilentlyContinue
            $item.Process.WaitForExit()
        }
    }
    if ($null -eq $priorNullAudio) {
        Remove-Item Env:JFG_PHASE9_NULL_AUDIO -ErrorAction SilentlyContinue
    } else {
        $env:JFG_PHASE9_NULL_AUDIO = $priorNullAudio
    }
}

$ordered = @($completed | Sort-Object Index)
if ($ordered.Count -ne $Runs) {
    throw "Only $($ordered.Count) of $Runs determinism runs completed"
}
$baseline = $ordered[0].HashPath
for ($index = 1; $index -lt $ordered.Count; ++$index) {
    $report = Join-Path $ordered[$index].Directory 'determinism-comparison.json'
    & python $comparator $baseline $ordered[$index].HashPath --output $report |
        Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 9 determinism diverged in run $($ordered[$index].Index); see $report"
    }
}

[pscustomobject]@{
    Status = 'pass'
    Runs = $Runs
    Parallelism = $Parallelism
    Baseline = $baseline
    ComparedRuns = $Runs - 1
}
