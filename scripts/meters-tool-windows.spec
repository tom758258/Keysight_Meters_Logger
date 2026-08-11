from __future__ import annotations

import argparse
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
args = parser.parse_args()

source_root = Path(args.source_root).resolve()
source_path = source_root / "src"

cli_analysis = Analysis(
    [str(source_path / "meters_tool_cli" / "cli.py")],
    pathex=[str(source_path)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
cli_pyz = PYZ(cli_analysis.pure)
cli_exe = EXE(
    cli_pyz,
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="meters-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)

launcher_analysis = Analysis(
    [str(source_path / "meters_tool_webui" / "launcher.py")],
    pathex=[str(source_path)],
    binaries=[],
    datas=[
        (
            str(source_path / "meters_tool_webui" / "static"),
            "meters_tool_webui/static",
        )
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
launcher_pyz = PYZ(launcher_analysis.pure)
launcher_exe = EXE(
    launcher_pyz,
    launcher_analysis.scripts,
    [],
    exclude_binaries=True,
    name="meters-tool-webui-launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)

bundle = COLLECT(
    cli_exe,
    launcher_exe,
    cli_analysis.binaries,
    cli_analysis.datas,
    launcher_analysis.binaries,
    launcher_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="meters-tool",
)
