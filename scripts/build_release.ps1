param(
    [string]$Version,
    [string]$ReleaseRoot = "release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

$packageVersion = Get-PackageVersion -Required
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $packageVersion
} elseif ($Version -ne $packageVersion) {
    throw "Version $Version does not match package version $packageVersion"
}

if ([System.IO.Path]::IsPathRooted($ReleaseRoot)) {
    $releaseRootFull = [System.IO.Path]::GetFullPath($ReleaseRoot)
} else {
    $releaseRootFull = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $ReleaseRoot))
}
$repoFull = [System.IO.Path]::GetFullPath($RepoRoot)
$repoPrefix = $repoFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not (
    $releaseRootFull.Equals($repoFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $releaseRootFull.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
)) {
    throw "ReleaseRoot must stay under the repository: $releaseRootFull"
}

$versionDir = [System.IO.Path]::GetFullPath((Join-Path $releaseRootFull $Version))
Assert-PathUnderRoot `
    -RootPath $releaseRootFull `
    -Path $versionDir `
    -Message "Version directory must stay under ReleaseRoot: {0}"
if (Test-Path -LiteralPath $versionDir) {
    Remove-Item -LiteralPath $versionDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $versionDir | Out-Null
$buildRoot = Join-Path $releaseRootFull ".build-$Version"
Assert-PathUnderRoot `
    -RootPath $releaseRootFull `
    -Path $buildRoot `
    -Message "Build directory must stay under ReleaseRoot: {0}"
if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}
$sourceRoot = Join-Path $buildRoot "source"
New-Item -ItemType Directory -Force -Path $sourceRoot | Out-Null
$trackedFiles = @(& git -C $RepoRoot -c core.quotepath=false ls-files)
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
foreach ($relativePath in $trackedFiles) {
    $sourcePath = Join-Path $RepoRoot $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        continue
    }
    $destinationPath = Join-Path $sourceRoot $relativePath
    $destinationParent = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath
}

$desktopPackagePath = Join-Path $sourceRoot "desktop\package.json"
$desktopPackage = Get-Content -Raw -LiteralPath $desktopPackagePath | ConvertFrom-Json
if ($desktopPackage.version -ne $Version) {
    throw "Desktop package version $($desktopPackage.version) does not match release version $Version"
}

& $Python -m build $sourceRoot --outdir $versionDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_desktop.ps1") -SourceRoot $sourceRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$desktopDirectory = Join-Path $sourceRoot "dist\desktop\win-unpacked"
if (-not (Test-Path -LiteralPath $desktopDirectory -PathType Container)) {
    throw "Desktop build did not produce release directory: $desktopDirectory"
}

$archiveRoot = Join-Path $buildRoot "windows-bundle-archive"
$versionedBundleDir = Join-Path $archiveRoot "meters-tool-$Version"
New-Item -ItemType Directory -Force -Path $versionedBundleDir | Out-Null
foreach ($entry in Get-ChildItem -LiteralPath $desktopDirectory -Force) {
    Copy-Item -LiteralPath $entry.FullName -Destination $versionedBundleDir -Recurse -Force
}

$windowsZipName = "meters-tool-$Version-windows-x64.zip"
$windowsZip = Join-Path $versionDir $windowsZipName
Compress-Archive `
    -LiteralPath $versionedBundleDir `
    -DestinationPath $windowsZip `
    -CompressionLevel Optimal

Remove-Item -LiteralPath $buildRoot -Recurse -Force

$expectedArtifactNames = @(
    $windowsZipName,
    "meters_tool-$Version-py3-none-any.whl",
    "meters_tool-$Version.tar.gz"
)
$releaseEntries = @(Get-ChildItem -LiteralPath $versionDir -Force)
$invalidEntries = @(
    $releaseEntries |
        Where-Object { $_.PSIsContainer -or $_.Name -notin $expectedArtifactNames }
)
if (
    $releaseEntries.Count -ne $expectedArtifactNames.Count -or
    $invalidEntries.Count -ne 0
) {
    $found = ($releaseEntries.Name | Sort-Object) -join ", "
    throw "Release build did not produce exactly the expected artifacts: $found"
}

$checksums = foreach ($artifactName in ($expectedArtifactNames | Sort-Object)) {
    $artifact = Get-Item -LiteralPath (Join-Path $versionDir $artifactName)
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName
    "$($hash.Hash.ToLowerInvariant())  $($artifact.Name)"
}
Write-Utf8NoBomLines -LiteralPath (Join-Path $versionDir "checksums.txt") -Lines $checksums

Write-Host "release artifacts: $versionDir"
