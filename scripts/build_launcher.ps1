[CmdletBinding()]
param([switch]$Test)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$launcherRepoRoot = Split-Path -Parent $PSScriptRoot
$launcherOutput = Join-Path $launcherRepoRoot 'build\launcher'
$launcherCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $launcherCompiler -PathType Leaf)) {
    throw 'The Windows x64 .NET Framework compiler is required.'
}
New-Item -ItemType Directory -Path $launcherOutput -Force | Out-Null
$launcherSource = Join-Path $launcherRepoRoot 'launcher\windows\Launcher.cs'
$launcherExe = Join-Path $launcherOutput 'JFG-Launcher.exe'
$launcherFirstRun = Join-Path $launcherRepoRoot 'launcher\windows\FirstRun.cs'
$launcherSetup = Join-Path $launcherRepoRoot 'launcher\windows\Setup.ps1'
$launcherCommit = (& git -C $launcherRepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $launcherCommit -notmatch '^[0-9a-f]{40}$') { throw 'Cannot pin launcher source revision.' }
$launcherBuildInfo = Join-Path $launcherOutput 'BuildInfo.cs'
[IO.File]::WriteAllText($launcherBuildInfo, 'namespace JfgLauncher { internal static class BuildInfo { internal const string SourceCommit = "' + $launcherCommit + '"; } }')
$launcherSources = @($launcherSource, $launcherFirstRun, $launcherBuildInfo,
    (Join-Path $launcherRepoRoot 'launcher/windows/Support.cs'), (Join-Path $launcherRepoRoot 'launcher/windows/Diagnostics.cs'), (Join-Path $launcherRepoRoot 'launcher/windows/Controller.cs'))
$launcherCommon = @('/nologo', '/optimize+', '/debug-', '/platform:x64', '/warnaserror+',
    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
    '/reference:System.Runtime.Serialization.dll', '/reference:System.IO.Compression.dll', "/resource:$launcherSetup,JfgLauncher.Setup.ps1")
& $launcherCompiler @launcherCommon '/target:winexe' "/out:$launcherExe" @launcherSources
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
if ($Test) {
    $launcherTests = Join-Path $launcherOutput 'LauncherTests.exe'
    $launcherTestSource = Join-Path $launcherRepoRoot 'launcher\windows\LauncherTests.cs'
    & $launcherCompiler @launcherCommon '/target:exe' '/main:JfgLauncher.LauncherTests' "/out:$launcherTests" @launcherSources $launcherTestSource
    if ($LASTEXITCODE -ne 0) { throw 'Launcher test compilation failed.' }
    & $launcherTests (Join-Path $launcherOutput 'launcher-preview.png')
    if ($LASTEXITCODE -ne 0) { throw 'Launcher tests failed.' }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $launcherRepoRoot 'launcher\windows\SetupTests.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'First-run setup tests failed.' }
}
$launcherInputs = [ordered]@{}
foreach ($relative in @('launcher/windows/Launcher.cs', 'launcher/windows/FirstRun.cs',
        'launcher/windows/Setup.ps1', 'launcher/windows/Support.cs', 'launcher/windows/Diagnostics.cs', 'launcher/windows/Controller.cs', 'scripts/build_launcher.ps1')) {
    $launcherInputs[$relative] = (Get-FileHash -LiteralPath (Join-Path $launcherRepoRoot $relative) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$launcherReceipt = [ordered]@{ source_commit = $launcherCommit;
    executable_sha256 = (Get-FileHash -LiteralPath $launcherExe -Algorithm SHA256).Hash.ToLowerInvariant(); inputs = $launcherInputs }
[IO.File]::WriteAllText((Join-Path $launcherOutput 'launcher-build.json'), ($launcherReceipt | ConvertTo-Json -Depth 4))
Write-Output 'Launcher built in build/launcher/JFG-Launcher.exe.'
