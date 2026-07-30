from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ACCEPTANCE = REPO_ROOT / "scripts" / "release-acceptance.ps1"
BUILD_RELEASE = REPO_ROOT / "scripts" / "build_release.ps1"
BUILD_CLI_EXE = REPO_ROOT / "scripts" / "build_cli_exe.ps1"
BUILD_WEBUI_EXE = REPO_ROOT / "scripts" / "build_webui_exe.ps1"
OLD_RELEASE_CHECK = REPO_ROOT / "scripts" / "release-cli-check.ps1"


def release_acceptance_text() -> str:
    return RELEASE_ACCEPTANCE.read_text(encoding="utf-8-sig")


def test_release_acceptance_replaces_cli_release_check():
    assert RELEASE_ACCEPTANCE.exists()
    assert not OLD_RELEASE_CHECK.exists()


def test_release_acceptance_keeps_target_and_package_version_guards():
    script = release_acceptance_text()

    for contract in (
        '[string]$Target = "keysight-34461a"',
        "$resolvedTarget = Resolve-ValidationTarget -Target $Target",
        "$targetModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget",
        '$Resource = "SIM::$targetModel"',
        "Release acceptance requires simulator resource",
        '$packageName -ne "meters-tool"',
        "$Release = $packageVersion",
        "Release $Release does not match package version $packageVersion",
    ):
        assert contract in script


def test_release_acceptance_checks_tools_lock_and_clean_git_tree():
    script = release_acceptance_text()

    for contract in (
        'Get-Command -Name "git"',
        'Get-Command -Name "uv"',
        "Project Python executable not found",
        '@("-m", "PyInstaller", "--version")',
        '@("lock", "--check")',
        '@("-C", $RepoRoot, "status", "--porcelain")',
        "Git working tree must be clean before release acceptance.",
    ):
        assert contract in script


def test_release_acceptance_runs_complete_no_hardware_suite():
    script = release_acceptance_text()

    assert '$script:currentStep = "pytest_no_hardware"' in script
    assert '"-m", "pytest", "tests"' in script
    assert '"--ignore=tests\\cli\\test_cli_wrappers.py"' not in script
    assert '"--basetemp", (Join-Path $runDir "pytest-no-hardware")' in script
    assert "pytest_metadata_docs" not in script


def test_release_acceptance_isolates_python_process_environment():
    script = release_acceptance_text()
    isolation_start = script.index('$env:PYTHONNOUSERSITE = "1"')
    pytest_start = script.index('$script:currentStep = "pytest_no_hardware"')
    isolation_block = script[isolation_start:pytest_start]

    assert "SetEnvironmentVariable(" in isolation_block
    assert "$null" in isolation_block
    assert "[EnvironmentVariableTarget]::Process" in isolation_block
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "UV_INTERNAL__PYTHONHOME",
        "UV_PROJECT_ENVIRONMENT",
    ):
        assert f'"{variable}"' in isolation_block


def test_release_acceptance_builds_release_once_without_direct_distribution_build():
    script = release_acceptance_text()

    assert script.count("build_release.ps1") == 1
    assert '@("-m", "build"' not in script


def test_release_acceptance_validates_final_artifacts_and_checksums():
    script = release_acceptance_text()

    for contract in (
        '"meters-tool-$packageVersion.exe"',
        '"meters-tool-webui-launcher-$packageVersion.exe"',
        '"meters_tool-$packageVersion-py3-none-any.whl"',
        '"meters_tool-$packageVersion.tar.gz"',
        '"checksums.txt"',
        "$releaseEntries.Count -ne $expectedReleaseNames.Count",
        "$checksumLines.Count -ne 4",
        "Get-FileHash -Algorithm SHA256",
        "SHA-256 mismatch",
        'Invoke-ArtifactSmoke -Label "wheel"',
        'Invoke-ArtifactSmoke -Label "sdist"',
        "import meters_tool_core, meters_tool_cli, meters_tool_webui",
        "from importlib.resources import files",
        "'index.html'",
        "'styles.css'",
        "'app.js'",
        "static_root.joinpath(name).is_file()",
        "assert not missing_static",
        "Scripts\\meters-tool.exe",
        "Scripts\\meters-tool-webui.exe",
        "Scripts\\meters-tool-webui-launcher.exe",
        "Path(sys.argv[1]).is_file()",
        '${Label}_launcher_entry_point',
    ):
        assert contract in script


def test_release_acceptance_runs_minimal_standalone_smokes_and_existing_preflight():
    script = release_acceptance_text()

    for contract in (
        '$script:currentStep = "standalone_cli_version"',
        '$script:currentStep = "standalone_cli_help"',
        '$script:currentStep = "standalone_cli_simulator"',
        '"--measurement", "current-dc"',
        '"--trigger-mode", "immediate"',
        '"--max-samples", "1"',
        '"--simulate"',
        '"--status-format", "jsonl"',
        'Where-Object { $_.event -eq "summary" }',
        "Test-CsvRowCount",
        '$script:currentStep = "launcher_self_test"',
        '@("--self-test")',
        ".\\scripts\\preflight-cli.ps1",
        ".\\scripts\\live-cli-check.ps1",
        '"-Suite"',
        '"minimal"',
        '"-PlanOnly"',
        '"-SkipPreflight"',
    ):
        assert contract in script


def test_release_acceptance_report_uses_project_release_semantics():
    script = release_acceptance_text()

    for contract in (
        'kind = "release_acceptance"',
        'name = "Meters Tool Release Acceptance"',
        'validation_mode = "release_acceptance_no_hardware"',
        "failed_step = $failedStep",
        "error = $failureMessage",
        "final_release_dir = $relativeFinalReleaseDir",
        "cli_exe = if ($null -ne $cliExe)",
        "webui_launcher_exe = if ($null -ne $launcherExe)",
        "checksum_validation = $checksumValidation",
        "standalone_cli_smoke = $standaloneCliSmoke",
        "launcher_self_test = $launcherSelfTest",
        "artifacts = $artifactItems",
        "commands = $commandItems",
    ):
        assert contract in script


def test_release_acceptance_keeps_output_under_tmp_tests():
    script = release_acceptance_text()

    assert '[string]$OutputRoot = ".tmp_tests\\release_acceptance"' in script
    assert "Assert-PathUnderRoot" in script
    assert "Only paths under .tmp_tests are allowed for release output" in script


def test_release_acceptance_rechecks_final_working_tree_hygiene():
    script = release_acceptance_text()
    plan_only_start = script.index('$script:currentStep = "live_cli_plan_only"')
    final_head_start = script.index('$script:currentStep = "git_head_final"')
    final_diff_start = script.index('$script:currentStep = "git_diff_check_final"')
    final_clean_start = script.index('$script:currentStep = "git_clean_final"')
    catch_start = script.index("} catch {", final_head_start)
    final_block = script[final_diff_start:catch_start]

    assert plan_only_start < final_diff_start < final_clean_start < final_head_start
    assert '@("-C", $RepoRoot, "rev-parse", "HEAD")' in final_block
    assert script.count('@("-C", $RepoRoot, "rev-parse", "HEAD")') == 2
    assert "$finalGitHead -cne $gitHead" in final_block
    assert "Git HEAD changed during release acceptance." in final_block
    assert '@("-C", $RepoRoot, "diff", "--check")' in final_block
    assert '@("-C", $RepoRoot, "status", "--porcelain")' in final_block
    assert script.count('@("-C", $RepoRoot, "status", "--porcelain")') == 2
    assert "Git working tree must remain clean after release acceptance." in final_block


def test_release_build_passes_one_source_snapshot_to_both_exe_builders():
    script = BUILD_RELEASE.read_text(encoding="utf-8-sig")

    assert '$sourceRoot = Join-Path $buildRoot "source"' in script
    assert script.count("-SourceRoot $sourceRoot") == 2
    for builder in ("build_cli_exe.ps1", "build_webui_exe.ps1"):
        invocation = next(line for line in script.splitlines() if builder in line)
        assert "-SourceRoot $sourceRoot" in invocation


def test_exe_builders_use_optional_source_root_for_pyinstaller_inputs():
    cli_script = BUILD_CLI_EXE.read_text(encoding="utf-8-sig")
    webui_script = BUILD_WEBUI_EXE.read_text(encoding="utf-8-sig")

    for script in (cli_script, webui_script):
        assert "[string]$SourceRoot" in script
        assert "$sourceRootFull = $repoFull" in script
        assert "SourceRoot directory not found" in script
        assert "SourceRoot must stay under the repository" in script
        assert '$sourcePath = Join-Path $sourceRootFull "src"' in script
        assert "$env:PYTHONPATH = $sourcePath" in script
        assert "--paths $sourcePath" in script

    assert (
        '(Join-Path $sourceRootFull "src\\meters_tool_cli\\cli.py")'
        in cli_script
    )
    assert (
        "$(Join-Path $sourceRootFull "
        "'src\\meters_tool_webui\\static');meters_tool_webui\\static"
        in webui_script
    )
    assert (
        '(Join-Path $sourceRootFull "src\\meters_tool_webui\\launcher.py")'
        in webui_script
    )
