param(
    [string]$DistPath = "dist",
    [string]$Name = "meters-tool-webui-launcher",
    [string]$WorkRoot = "build",
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

if ([System.IO.Path]::IsPathRooted($DistPath)) {
    $distFull = [System.IO.Path]::GetFullPath($DistPath)
} else {
    $distFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $DistPath))
}
$repoFull = [System.IO.Path]::GetFullPath($RepoRoot)
$repoPrefix = $repoFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not (
    $distFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $distFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "DistPath must stay under the repository: $distFull"
}
if ([System.IO.Path]::IsPathRooted($WorkRoot)) {
    $workRootFull = [System.IO.Path]::GetFullPath($WorkRoot)
} else {
    $workRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $WorkRoot))
}
if (-not $workRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "WorkRoot must stay under the repository: $workRootFull"
}
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $sourceRootFull = $repoFull
} elseif ([System.IO.Path]::IsPathRooted($SourceRoot)) {
    $sourceRootFull = [System.IO.Path]::GetFullPath($SourceRoot)
} else {
    $sourceRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $SourceRoot))
}
if (-not (Test-Path -LiteralPath $sourceRootFull -PathType Container)) {
    throw "SourceRoot directory not found: $sourceRootFull"
}
$sourceRootFull = (Resolve-Path -LiteralPath $sourceRootFull).Path
if (-not (
    $sourceRootFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $sourceRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "SourceRoot must stay under the repository: $sourceRootFull"
}
$sourcePath = Join-Path $sourceRootFull "src"
$previousPythonPath = $env:PYTHONPATH

try {
    $env:PYTHONPATH = $sourcePath
    & $Python -m PyInstaller `
        --onefile `
        --windowed `
        --name $Name `
        --distpath $distFull `
        --workpath (Join-Path $workRootFull "pyinstaller-webui") `
        --specpath (Join-Path $workRootFull "pyinstaller-specs") `
        --paths $sourcePath `
        --add-data "$(Join-Path $sourceRootFull 'src\meters_tool_webui\static');meters_tool_webui\static" `
        (Join-Path $sourceRootFull "src\meters_tool_webui\launcher.py")
    $pyinstallerExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

if ($pyinstallerExitCode -ne 0) {
    exit $pyinstallerExitCode
}
