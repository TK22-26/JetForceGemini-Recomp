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
$launcherCommon = @('/nologo', '/optimize+', '/debug-', '/platform:x64', '/warnaserror+',
    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
    '/reference:System.Runtime.Serialization.dll')
& $launcherCompiler @launcherCommon '/target:winexe' "/out:$launcherExe" $launcherSource
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
if ($Test) {
    $launcherTests = Join-Path $launcherOutput 'LauncherTests.exe'
    $launcherTestSource = Join-Path $launcherRepoRoot 'launcher\windows\LauncherTests.cs'
    & $launcherCompiler @launcherCommon '/target:exe' '/main:JfgLauncher.LauncherTests' "/out:$launcherTests" $launcherSource $launcherTestSource
    if ($LASTEXITCODE -ne 0) { throw 'Launcher test compilation failed.' }
    & $launcherTests (Join-Path $launcherOutput 'launcher-preview.png')
    if ($LASTEXITCODE -ne 0) { throw 'Launcher tests failed.' }
}
Write-Output 'Launcher built in build/launcher/JFG-Launcher.exe.'
