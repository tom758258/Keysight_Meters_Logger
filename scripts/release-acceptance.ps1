param(
    [string]$Target = "keysight-34461a",

    [string]$Release,

    [string]$Resource,

    [string]$OutputRoot = ".tmp_tests\release_acceptance"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TmpRoot = Join-Path $RepoRoot ".tmp_tests"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
. (Join-Path $PSScriptRoot "_validation_helpers.ps1")

function Get-PackageName {
    $pyproject = Join-Path $RepoRoot "pyproject.toml"
    $match = Select-String -LiteralPath $pyproject -Pattern '^name\s*=\s*"([^"]+)"' |
        Select-Object -First 1
    if ($null -eq $match) {
        throw "Could not read project name from $pyproject"
    }
    return $match.Matches[0].Groups[1].Value
}

function Assert-UnderTmpRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    Assert-PathUnderRoot `
        -RootPath $TmpRoot `
        -Path $Path `
        -Message "Only paths under .tmp_tests are allowed for release output: {0}"
}

function Resolve-OutputRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $resolved = Get-FullPath $Path
    } else {
        $resolved = Get-FullPath (Join-Path $RepoRoot $Path)
    }
    Assert-UnderTmpRoot -Path $resolved
    return $resolved
}

function Get-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $fullPath = Get-FullPath $Path
    $repoPrefix = $RepoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the repository: $fullPath"
    }
    return $fullPath.Substring($repoPrefix.Length).Replace("\", "/")
}

$resolvedTarget = Resolve-ValidationTarget -Target $Target
$targetModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget
if ([string]::IsNullOrWhiteSpace($Resource)) {
    $Resource = "SIM::$targetModel"
}
$expectedSimulatorResource = "SIM::$targetModel"
if (-not $Resource.Equals($expectedSimulatorResource, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release acceptance requires simulator resource $expectedSimulatorResource."
}

$packageName = Get-PackageName
if ($packageName -ne "meters-tool") {
    throw "Package name $packageName does not match expected project name meters-tool"
}
$packageVersion = Get-PackageVersion -Required
if ([string]::IsNullOrWhiteSpace($Release)) {
    $Release = $packageVersion
} elseif ($Release -ne $packageVersion) {
    throw "Release $Release does not match package version $packageVersion"
}

$releaseRoot = Resolve-OutputRoot -Path $OutputRoot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$runDir = Join-Path (Join-Path $releaseRoot $resolvedTarget) $timestamp
Assert-UnderTmpRoot -Path $runDir
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$reportPath = Join-Path $runDir "report.json"
$summaryPath = Join-Path $runDir "summary.md"
$checksumsPath = Join-Path $runDir "checksums.txt"
$commands = [System.Collections.Generic.List[object]]::new()
$artifacts = [System.Collections.Generic.List[object]]::new()
$script:currentStep = "initialize"
$failedStep = $null
$failureMessage = $null
$gitHead = $null
$wheel = $null
$sdist = $null

function Invoke-RecordedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $stdout = Join-Path $runDir "$Name.stdout.txt"
    $stderr = Join-Path $runDir "$Name.stderr.txt"
    $result = [pscustomobject](Invoke-CapturedCommand `
        -Name $Name `
        -FilePath $FilePath `
        -Arguments $Arguments `
        -StdOutPath $stdout `
        -StdErrPath $stderr)
    $result | Add-Member -NotePropertyName error -NotePropertyValue $null
    $commands.Add($result) | Out-Null
    if (-not $result.success) {
        throw "Step '$Name' failed with exit code $($result.exit_code)."
    }
    return $result
}

function Set-RecordedCommandFailure {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $true)][string]$Message
    )
    $Result.success = $false
    $Result.error = $Message
    throw $Message
}

function Invoke-ArtifactSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$Artifact,
        [Parameter(Mandatory = $true)][string]$UvPath
    )

    $venvDir = Join-Path $runDir "$Label-venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $cliCommand = Join-Path $venvDir "Scripts\meters-tool.exe"
    $webuiCommand = Join-Path $venvDir "Scripts\meters-tool-webui.exe"
    $artifactSpec = "$($Artifact.FullName)[all]"

    $script:currentStep = "${Label}_create_venv"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("-m", "venv", $venvDir))

    $script:currentStep = "${Label}_install"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $UvPath `
        -Arguments @("pip", "install", "--python", $venvPython, "--link-mode", "copy", $artifactSpec))

    $script:currentStep = "${Label}_imports_and_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $venvPython `
        -Arguments @(
            "-c",
            "import sys; from importlib.metadata import version; import meters_tool_core, meters_tool_cli, meters_tool_webui; assert version('meters-tool') == sys.argv[1]",
            $packageVersion
        ))

    $script:currentStep = "${Label}_cli_version"
    $versionResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliCommand `
        -Arguments @("--version")
    $versionOutput = (Get-Content -Raw -LiteralPath $versionResult.stdout).Trim()
    if ($versionOutput -ne "meters-tool $packageVersion") {
        Set-RecordedCommandFailure `
            -Result $versionResult `
            -Message "Installed CLI version was '$versionOutput'; expected 'meters-tool $packageVersion'."
    }

    $script:currentStep = "${Label}_cli_help"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $cliCommand `
        -Arguments @("--help"))

    $script:currentStep = "${Label}_webui_help"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $webuiCommand `
        -Arguments @("--help"))
}

try {
    $script:currentStep = "required_tools"
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Project Python executable not found: $Python"
    }
    $gitCommand = Get-Command -Name "git" -CommandType Application -ErrorAction Stop
    $uvCommand = Get-Command -Name "uv" -CommandType Application -ErrorAction Stop

    $script:currentStep = "git_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "uv_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $uvCommand.Source `
        -Arguments @("--version"))

    $script:currentStep = "python_version"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("--version"))

    $script:currentStep = "git_clean"
    $gitStatusResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "status", "--porcelain")
    $gitStatus = Get-Content -Raw -LiteralPath $gitStatusResult.stdout

    $script:currentStep = "git_head"
    $gitHeadResult = Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $gitCommand.Source `
        -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $gitHead = (Get-Content -Raw -LiteralPath $gitHeadResult.stdout).Trim()
    if ([string]::IsNullOrWhiteSpace($gitHead)) {
        throw "Could not resolve Git HEAD."
    }
    if (-not [string]::IsNullOrWhiteSpace($gitStatus)) {
        $script:currentStep = "git_clean"
        Set-RecordedCommandFailure `
            -Result $gitStatusResult `
            -Message "Git working tree must be clean before release acceptance."
    }

    $script:currentStep = "uv_lock_check"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $uvCommand.Source `
        -Arguments @("lock", "--check"))

    $script:currentStep = "pytest_fast"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @(
            "-m", "pytest", "tests",
            "-q", "-p", "no:cacheprovider",
            "--ignore=tests\cli\test_cli_wrappers.py",
            "--basetemp", (Join-Path $runDir "pytest-fast")
        ))

    $script:currentStep = "prepare_build_output"
    $buildRoot = Join-Path $runDir "build"
    $artifactDir = Join-Path $buildRoot "dist"
    Assert-UnderTmpRoot -Path $buildRoot
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

    $script:currentStep = "build_distribution"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath $Python `
        -Arguments @("-m", "build", "--outdir", $artifactDir))

    $script:currentStep = "validate_artifacts"
    $artifactFiles = @(Get-ChildItem -LiteralPath $artifactDir -File)
    $wheelCandidates = @(
        $artifactFiles |
            Where-Object {
                $_.Name.StartsWith("meters_tool-$packageVersion-") -and
                $_.Name.EndsWith(".whl")
            }
    )
    $sdistCandidates = @(
        $artifactFiles |
            Where-Object { $_.Name -eq "meters_tool-$packageVersion.tar.gz" }
    )
    if (
        $artifactFiles.Count -ne 2 -or
        $wheelCandidates.Count -ne 1 -or
        $sdistCandidates.Count -ne 1
    ) {
        $found = ($artifactFiles.Name | Sort-Object) -join ", "
        throw "Expected one wheel and one sdist for meters-tool $packageVersion; found: $found"
    }
    $wheel = $wheelCandidates[0]
    $sdist = $sdistCandidates[0]

    $checksumLines = @()
    foreach ($artifact in @($wheel, $sdist)) {
        $artifactType = if ($artifact.Extension -eq ".whl") { "wheel" } else { "sdist" }
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName).Hash.ToLowerInvariant()
        $relativePath = Get-RepoRelativePath -Path $artifact.FullName
        $artifacts.Add([pscustomobject][ordered]@{
            type = $artifactType
            path = $relativePath
            filename = $artifact.Name
            sha256 = $hash
            package_version = $packageVersion
        }) | Out-Null
        $checksumLines += "$hash  $($artifact.Name)"
    }
    Write-Utf8NoBomLines -LiteralPath $checksumsPath -Lines $checksumLines

    Invoke-ArtifactSmoke -Label "wheel" -Artifact $wheel -UvPath $uvCommand.Source
    Invoke-ArtifactSmoke -Label "sdist" -Artifact $sdist -UvPath $uvCommand.Source

    $script:currentStep = "preflight_cli"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ".\scripts\preflight-cli.ps1",
            "-Target",
            $resolvedTarget,
            "-OutputRoot",
            (Join-Path $runDir "preflight")
        ))

    $script:currentStep = "live_cli_plan_only"
    [void](Invoke-RecordedCommand `
        -Name $script:currentStep `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ".\scripts\live-cli-check.ps1",
            "-Target",
            $resolvedTarget,
            "-Connection",
            "usb",
            "-Resource",
            $Resource,
            "-PlanOnly",
            "-SkipPreflight"
        ))
} catch {
    $failedStep = $script:currentStep
    $failureMessage = $_.Exception.Message
}

$commandItems = @($commands.ToArray())
$artifactItems = @($artifacts.ToArray())
$status = if ($null -eq $failedStep) { "passed" } else { "failed" }
$relativeReportPath = Get-RepoRelativePath -Path $reportPath
$relativeSummaryPath = Get-RepoRelativePath -Path $summaryPath
$relativeOutputDir = Get-RepoRelativePath -Path $runDir

$report = [ordered]@{
    schema_version = 1
    kind = "release_acceptance"
    name = "Meters Tool Release Acceptance"
    target_release = $Release
    package_name = $packageName
    package_version = $packageVersion
    git_head = $gitHead
    target = $resolvedTarget
    model_id = $resolvedTarget
    expected_model = $targetModel
    resource = $Resource
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    validation_mode = "release_acceptance_no_hardware"
    output_dir = $relativeOutputDir
    artifact_paths = [ordered]@{
        output_dir = $relativeOutputDir
        report = $relativeReportPath
        summary = $relativeSummaryPath
        checksums = if (Test-Path -LiteralPath $checksumsPath) {
            Get-RepoRelativePath -Path $checksumsPath
        } else {
            $null
        }
        wheel = if ($null -ne $wheel) { Get-RepoRelativePath -Path $wheel.FullName } else { $null }
        sdist = if ($null -ne $sdist) { Get-RepoRelativePath -Path $sdist.FullName } else { $null }
    }
    artifacts = $artifactItems
    status = $status
    failed_step = $failedStep
    error = $failureMessage
    commands = $commandItems
}
Write-JsonReport -LiteralPath $reportPath -Report $report -Depth 12

$summaryLines = @(
    "# Meters Tool Release Acceptance Summary",
    "",
    "- Package: $packageName $packageVersion",
    "- Target release: $Release",
    "- Target: $resolvedTarget",
    "- Expected model: $targetModel",
    "- Resource: $Resource",
    "- Git HEAD: $gitHead",
    "- Status: $status",
    "- Validation mode: release_acceptance_no_hardware",
    "- Output directory: $relativeOutputDir",
    "- Report: $relativeReportPath"
)
if ($null -ne $failedStep) {
    $summaryLines += "- Failed step: $failedStep"
    $summaryLines += "- Error: $failureMessage"
}
$summaryLines += @(
    "",
    "## Artifacts"
)
if ($artifactItems.Count -eq 0) {
    $summaryLines += "- No validated artifacts."
} else {
    foreach ($artifact in $artifactItems) {
        $summaryLines += "- $($artifact.type): $($artifact.filename) sha256=$($artifact.sha256)"
    }
}
$summaryLines += @(
    "",
    "## Commands"
)
foreach ($command in $commandItems) {
    $summaryLines += "- $($command.name): exit_code=$($command.exit_code) success=$($command.success)"
}
Write-Utf8NoBomLines -LiteralPath $summaryPath -Lines $summaryLines

Write-Host "release acceptance $status`: $Release"
Write-Host "summary: $relativeSummaryPath"
if ($status -ne "passed") {
    exit 1
}
