from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ACCEPTANCE = REPO_ROOT / "scripts" / "release-acceptance.ps1"
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
        '@("lock", "--check")',
        '@("-C", $RepoRoot, "status", "--porcelain")',
        "Git working tree must be clean before release acceptance.",
    ):
        assert contract in script


def test_release_acceptance_runs_fast_suite_without_wrapper_tests():
    script = release_acceptance_text()

    assert '"-m", "pytest", "tests"' in script
    assert '"--ignore=tests\\cli\\test_cli_wrappers.py"' in script
    assert '"--basetemp", (Join-Path $runDir "pytest-fast")' in script
    assert "pytest_metadata_docs" not in script


def test_release_acceptance_covers_artifacts_smokes_wrappers_and_checksums():
    script = release_acceptance_text()

    for contract in (
        '@("-m", "build", "--outdir", $artifactDir)',
        'StartsWith("meters_tool-$packageVersion-")',
        'Name -eq "meters_tool-$packageVersion.tar.gz"',
        'Invoke-ArtifactSmoke -Label "wheel"',
        'Invoke-ArtifactSmoke -Label "sdist"',
        "import meters_tool_core, meters_tool_cli, meters_tool_webui",
        "Scripts\\meters-tool.exe",
        "Scripts\\meters-tool-webui.exe",
        "Get-FileHash -Algorithm SHA256",
        ".\\scripts\\preflight-cli.ps1",
        ".\\scripts\\live-cli-check.ps1",
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
        "artifacts = $artifactItems",
        "commands = $commandItems",
    ):
        assert contract in script


def test_release_acceptance_keeps_output_under_tmp_tests():
    script = release_acceptance_text()

    assert '[string]$OutputRoot = ".tmp_tests\\release_acceptance"' in script
    assert "Assert-PathUnderRoot" in script
    assert "Only paths under .tmp_tests are allowed for release output" in script
