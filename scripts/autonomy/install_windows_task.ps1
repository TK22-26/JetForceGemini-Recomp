param(
    [ValidateSet('Plan', 'Install', 'Status', 'Remove')]
    [string]$Action = 'Plan',
    [string]$TaskName = 'JFG Autonomous Supervisor',
    [ValidateRange(0, 100)]
    [int]$MaxAgentAttemptsPerDay = 0,
    [ValidateRange(1, 300)]
    [int]$PollSeconds = 15,
    [string]$PythonBin,
    [string]$CodexBin,
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'
if ($TaskName -notmatch '^[A-Za-z0-9][A-Za-z0-9 ._-]{0,127}$') {
    throw 'Task name must be a literal name without wildcards or a task path.'
}
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$state = Join-Path $repo 'tools\private\autonomy'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if (-not $PythonBin) {
    $PythonBin = (Get-Command python.exe -CommandType Application -ErrorAction Stop).Source
}
if (-not $CodexBin) {
    $CodexBin = (Get-Command codex.cmd -CommandType Application -ErrorAction Stop).Source
}
$PythonBin = (Resolve-Path -LiteralPath $PythonBin).Path
$CodexBin = (Resolve-Path -LiteralPath $CodexBin).Path

function Quote-TaskArgument([string]$value) {
    if ($value.Contains('"')) { throw 'Task argument contains a quote.' }
    return '"' + $value + '"'
}

$arguments = @(
    '-m', 'scripts.autonomy.service_entry',
    '--repo', (Quote-TaskArgument $repo),
    '--state', (Quote-TaskArgument $state),
    '--codex-bin', (Quote-TaskArgument $CodexBin),
    '--max-agent-attempts-per-day', [string]$MaxAgentAttemptsPerDay,
    '--poll-seconds', [string]$PollSeconds
) -join ' '
$existing = Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue
$owned = ($null -ne $existing -and $existing.Actions.Count -eq 1 -and
          $existing.Actions[0].Arguments -like '*scripts.autonomy.service_entry*' -and
          $existing.Actions[0].WorkingDirectory -eq $repo)
if ($existing -and $existing.State -eq 'Running' -and
    $Action -in @('Install', 'Remove')) {
    throw 'Refusing to replace or remove a running supervisor task.'
}

if ($Action -eq 'Plan') {
    [pscustomobject]@{
        task_name = $TaskName
        repository = $repo
        python = $PythonBin
        arguments = $arguments
        principal = $identity
        triggers = @('current-user logon', 'daily 03:00 watchdog')
        agent_attempt_cap_per_utc_day = $MaxAgentAttemptsPerDay
        existing_task = $null -ne $existing
        existing_task_owned = $owned
        installed = $false
    } | ConvertTo-Json -Depth 3
    return
}
if ($Action -eq 'Status') {
    [pscustomobject]@{
        task_name = $TaskName
        exists = $null -ne $existing
        owned = $owned
        state = if ($existing) { [string]$existing.State } else { $null }
    } | ConvertTo-Json
    return
}
if ($Action -eq 'Remove') {
    if (-not $existing) { throw 'Task does not exist.' }
    if (-not $owned) { throw 'Refusing to remove an unrecognized task.' }
    Unregister-ScheduledTask -TaskPath '\' -TaskName $TaskName -Confirm:$false
    Write-Output "Removed owned task: $TaskName"
    return
}
if ($existing -and (-not $owned -or -not $Replace)) {
    throw 'Task already exists; replacement requires an owned task and -Replace.'
}
$taskAction = New-ScheduledTaskAction -Execute $PythonBin -Argument $arguments -WorkingDirectory $repo
$logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
$watchdog = New-ScheduledTaskTrigger -Daily -At '03:00'
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$registration = @{
    TaskPath = '\'
    TaskName = $TaskName
    Action = $taskAction
    Trigger = @($logon, $watchdog)
    Principal = $principal
    Settings = $settings
    Description = 'Bounded, private Jet Force Gemini automation supervisor.'
}
if ($Replace) { $registration.Force = $true }
Register-ScheduledTask @registration | Out-Null
$installed = Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction Stop
if ($installed.Actions.Count -ne 1 -or
    $installed.Actions[0].Execute -ne $PythonBin -or
    $installed.Actions[0].Arguments -ne $arguments) {
    throw 'Registered task does not match the planned action.'
}
Write-Output "Installed task: $TaskName (agent attempts/day: $MaxAgentAttemptsPerDay)"
