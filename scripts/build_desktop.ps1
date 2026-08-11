param(
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BackendBuild = Join-Path $PSScriptRoot "build_desktop_backend.ps1"

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $sourceRootFull = $RepoRoot
} elseif ([System.IO.Path]::IsPathRooted($SourceRoot)) {
    $sourceRootFull = [System.IO.Path]::GetFullPath($SourceRoot)
} else {
    $sourceRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $SourceRoot))
}
if (-not (Test-Path -LiteralPath $sourceRootFull -PathType Container)) {
    throw "SourceRoot directory not found: $sourceRootFull"
}
$sourceRootFull = (Resolve-Path -LiteralPath $sourceRootFull).Path
$DesktopRoot = Join-Path $sourceRootFull "desktop"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BackendBuild -SourceRoot $sourceRootFull
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Npm = Get-Command -Name "npm.cmd" -CommandType Application -ErrorAction Stop |
    Select-Object -First 1
Push-Location $DesktopRoot
try {
    & $Npm.Source ci
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $Npm.Source run check
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $Npm.Source run dist:win
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$Package = Get-Content -Raw -LiteralPath (Join-Path $DesktopRoot "package.json") |
    ConvertFrom-Json
$Artifact = Join-Path $sourceRootFull (
    "dist\desktop\Meters-Tool-Desktop-{0}-portable.exe" -f $Package.version
)
if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) {
    throw "Desktop portable build did not produce: $Artifact"
}

Write-Host "Desktop portable artifact: $Artifact"
