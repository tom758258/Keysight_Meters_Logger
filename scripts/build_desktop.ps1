param(
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$WindowsBundleBuild = Join-Path $PSScriptRoot "build_windows_bundle.ps1"

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
$DistRoot = Join-Path $sourceRootFull "dist"
$BuildRoot = Join-Path $sourceRootFull "build"
$DesktopDist = Join-Path $DistRoot "desktop"
$SharedBundle = Join-Path $DistRoot "meters-tool"
$DesktopDirectory = Join-Path $DesktopDist "win-unpacked"
$sourceRootPrefix = $sourceRootFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar

foreach ($ownedPath in @(
    $DesktopDist,
    $SharedBundle
)) {
    $ownedPathFull = [System.IO.Path]::GetFullPath($ownedPath)
    if (-not $ownedPathFull.StartsWith(
        $sourceRootPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Desktop build path must stay under SourceRoot: $ownedPathFull"
    }
    if (Test-Path -LiteralPath $ownedPathFull) {
        Remove-Item -LiteralPath $ownedPathFull -Recurse -Force
    }
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $WindowsBundleBuild `
    -DistPath $DistRoot `
    -WorkRoot $BuildRoot `
    -SourceRoot $sourceRootFull
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

if (-not (Test-Path -LiteralPath $DesktopDirectory -PathType Container)) {
    throw "Electron directory build did not produce: $DesktopDirectory"
}
if (-not (Test-Path -LiteralPath $SharedBundle -PathType Container)) {
    throw "Shared Windows bundle not found: $SharedBundle"
}

foreach ($entry in Get-ChildItem -LiteralPath $SharedBundle -Force) {
    Copy-Item -LiteralPath $entry.FullName -Destination $DesktopDirectory -Recurse -Force
}

foreach ($requiredPath in @(
    (Join-Path $DesktopDirectory "Meters Tool.exe"),
    (Join-Path $DesktopDirectory "meters-tool.exe"),
    (Join-Path $DesktopDirectory "meters-tool-webui-launcher.exe"),
    (Join-Path $DesktopDirectory "meters-tool-webui-host.exe")
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Desktop directory is missing required executable: $requiredPath"
    }
}

$internalDirectories = @(
    Get-ChildItem -LiteralPath $DesktopDirectory -Directory -Recurse -Force |
        Where-Object { $_.Name -eq "_internal" }
)
if ($internalDirectories.Count -ne 1) {
    throw "Desktop directory must contain exactly one _internal directory."
}
if (-not $internalDirectories[0].FullName.Equals(
    (Join-Path $DesktopDirectory "_internal"),
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Desktop _internal directory must be shared at the application root."
}
$cliHelpDirectory = Join-Path $DesktopDirectory "_internal\meters_tool_cli\help"
if (-not (Test-Path -LiteralPath $cliHelpDirectory -PathType Container)) {
    throw "CLI Help directory missing: $cliHelpDirectory"
}
foreach ($name in @("cli.html", "cli.zh-TW.html", "supported-models.html", "supported-models.zh-TW.html", "help.css")) {
    $helpFile = Join-Path $cliHelpDirectory $name
    if (-not (Test-Path -LiteralPath $helpFile -PathType Leaf)) {
        throw "CLI Help file missing: $helpFile"
    }
}
$webuiHelpDirectory = Join-Path $DesktopDirectory "_internal\meters_tool_webui\static\help"
if (-not (Test-Path -LiteralPath $webuiHelpDirectory -PathType Container)) {
    throw "WebUI Help directory missing: $webuiHelpDirectory"
}
foreach ($name in @("webui.html", "webui.zh-TW.html", "supported-models.html", "supported-models.zh-TW.html", "help.css")) {
    $helpFile = Join-Path $webuiHelpDirectory $name
    if (-not (Test-Path -LiteralPath $helpFile -PathType Leaf)) {
        throw "WebUI Help file missing: $helpFile"
    }
}
if (Test-Path -LiteralPath (Join-Path $cliHelpDirectory "webui.html") -PathType Leaf) {
    throw "CLI Help must not contain webui.html: $(Join-Path $cliHelpDirectory 'webui.html')"
}
if (Test-Path -LiteralPath (Join-Path $cliHelpDirectory "webui.zh-TW.html") -PathType Leaf) {
    throw "CLI Help must not contain webui.zh-TW.html: $(Join-Path $cliHelpDirectory 'webui.zh-TW.html')"
}
if (Test-Path -LiteralPath (Join-Path $webuiHelpDirectory "cli.html") -PathType Leaf) {
    throw "WebUI Help must not contain cli.html: $(Join-Path $webuiHelpDirectory 'cli.html')"
}
if (Test-Path -LiteralPath (Join-Path $webuiHelpDirectory "cli.zh-TW.html") -PathType Leaf) {
    throw "WebUI Help must not contain cli.zh-TW.html: $(Join-Path $webuiHelpDirectory 'cli.zh-TW.html')"
}
if (Test-Path -LiteralPath (Join-Path $DesktopDirectory "meters_tool_cli\help") -PathType Container) {
    throw "Duplicate Help outside _internal: $(Join-Path $DesktopDirectory 'meters_tool_cli\help')"
}
if (Test-Path -LiteralPath (Join-Path $DesktopDirectory "meters_tool_webui\static\help") -PathType Container) {
    throw "Duplicate Help outside _internal: $(Join-Path $DesktopDirectory 'meters_tool_webui\static\help')"
}
if (Test-Path -LiteralPath (Join-Path $DesktopDirectory "resources\backend")) {
    throw "Desktop directory must not contain resources\backend."
}
if (@(Get-ChildItem -LiteralPath $DesktopDist -Filter "*-portable.exe" -File -Recurse).Count -ne 0) {
    throw "Desktop directory build must not produce a portable executable."
}

Write-Host "Desktop directory: $DesktopDirectory"
