Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SourcePath = Join-Path $RepoRoot "src"
$HostScript = Join-Path $SourcePath "meters_tool_webui\_desktop_host.py"
$StaticPath = Join-Path $SourcePath "meters_tool_webui\static"
$DistPath = Join-Path $RepoRoot "build\desktop-backend-dist"
$WorkPath = Join-Path $RepoRoot "build\pyinstaller-desktop-backend"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python"
}
if (-not (Test-Path -LiteralPath $HostScript -PathType Leaf)) {
    throw "Desktop WebUI host not found: $HostScript"
}
if (-not (Test-Path -LiteralPath $StaticPath -PathType Container)) {
    throw "WebUI static directory not found: $StaticPath"
}

$pythonBits = (& $Python -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
if ($pythonBits -ne "64") {
    throw "Windows x64 Desktop backend requires a 64-bit Python environment."
}

New-Item -ItemType Directory -Force -Path $WorkPath | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --console `
    --contents-directory "_internal" `
    --name "meters-tool-webui-host" `
    --distpath $DistPath `
    --workpath (Join-Path $WorkPath "work") `
    --specpath $WorkPath `
    --paths $SourcePath `
    --add-data "$StaticPath;meters_tool_webui/static" `
    $HostScript
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$BackendExe = Join-Path $DistPath "meters-tool-webui-host\meters-tool-webui-host.exe"
if (-not (Test-Path -LiteralPath $BackendExe -PathType Leaf)) {
    throw "Desktop backend build did not produce: $BackendExe"
}

Write-Host "Desktop backend: $BackendExe"
