[English](README.md)

# Meters Tool

Meters Tool 是供支援的數位萬用電表使用的 Python 資料擷取與紀錄工具。目前版本支援 Keysight 34460A 與 34461A；確切的驗證範圍請參閱 [支援型號文件](docs/core/supported-models.md)。專案提供單一可安裝發行套件 `meters-tool`，其套件版本由根目錄 `pyproject.toml` 定義，同時保留三個獨立的 import package：`meters_tool_core`、`meters_tool_cli` 與 `meters_tool_webui`。

本專案支援透過 VISA 進行 DC 與 AC 電流、DC 與 AC 電壓、DC 電壓比、頻率、週期，以及 2 線式或 4 線式電阻量測。每筆擷取的樣本都會寫入 CSV 的一行，包含時間戳記、量測類型、單位、觸發來源與相關 metadata。

實體儀器連線需要另外安裝相容的 VISA 實作。Meters Tool 不包含系統 VISA 執行環境；dry-run 與模擬模式則不需要安裝 VISA。

## 功能特性

* 透過 VISA 控制支援的數位萬用電表
* 設定量測範圍 (range)、NPLC、Auto Zero、AC 頻寬 (bandwidth)、電流端子 (current terminal) 與 DC 電壓輸入阻抗 (input impedance)
* 支援 software 工作流程（可透過 `--timer-interval-s` 選用計時排程）、external hardware、immediate 與 custom/buffered 觸發工作流程
* 使用 dry-run 模式預覽儀器命令
* 使用內建模擬器在沒有硬體的情況下測試工作流程
* 透過 CLI 或本機 WebUI 進行操作
* 在瀏覽器 WebUI 中即時切換英文與繁體中文，不需重新載入頁面，也不會重設目前執行、表單值、即時樣本、圖表、狀態或其他執行階段 UI 狀態；手動選擇會保存在瀏覽器中
* 產生 JSON 與 JSONL 輸出，供自動化、agent 與 orchestrator 使用

實機啟動時會透過 `*IDN?` 自動偵測已連接的型號；明確選擇的型號僅作為預期型號防護 (expected-model guard)，並不會為另一台儀器解鎖功能。精確的實機支援採用 fail-closed (預設關閉) 原則；關於型號、傳輸/後端、量測與觸發模式的狀態，請參閱 [支援型號](docs/core/supported-models.md) 與各元件說明文件。

## 專案結構

此 repository 現在使用單一發行套件與單一版本號。在範例中，`<version>` 代表根目錄 `pyproject.toml` 中的 `[project].version`：

* 發行套件 (Distribution)：`meters-tool` `<version>`
* Core import：`meters_tool_core`
* CLI import：`meters_tool_cli`
* WebUI import：`meters_tool_webui`

import 路徑彼此獨立。請不要使用 `meters_tool.*` namespace package。

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
tests/
  core/
  cli/
  webui/
docs/
  core/
  cli/
  webui/
scripts/
```

## 安裝

首先開啟 PowerShell 並進入專案根目錄：

```powershell
cd path\to\meters-tool
```

如果尚未安裝 uv，請先安裝：

```powershell
py -m pip install --user uv
```

驗證 uv：

```powershell
uv --version
```

在專案資料夾中建立虛擬環境：

```powershell
uv venv .venv
```

依照 `uv.lock` 同步可重現的開發與測試環境：

```powershell
uv sync --all-extras --link-mode=copy
```

針對 CI 或嚴格的本機檢查，可要求已提交的 lock 檔案保持不變：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

本專案支援 Python `>=3.10`。`uv venv .venv` 會使用可用的相容 Python。如果您需要特定的 Python 版本，請明確指定：

```powershell
uv venv .venv --python 3.12
```

`uv.lock` 檔案用於 uv 的開發與 CI 可重現環境。

Windows 會建立 virtualenv console wrappers，例如
`.\.venv\Scripts\meters-tool.exe`、
`.\.venv\Scripts\meters-tool-webui.exe` 與
`.\.venv\Scripts\meters-tool-webui-launcher.exe`。

如果既有虛擬環境已完成同步，但仍缺少一個或多個 console wrapper，請強制 uv 只重新安裝本專案套件：

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

這會重新建置專案套件並重建 console wrappers，不需要 pip。新建立的虛擬環境通常不需要執行此命令。

## 快速開始

安裝後，可在沒有硬體的情況下執行安全的模擬器工作流程：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource SIM::34461A `
  --simulate `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv .tmp_tests\quick-start-simulator.csv `
  --status-format jsonl
```

啟動 WebUI 主控台伺服器：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

或啟動 WebUI launcher：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

Launcher 只會繫結本機 loopback。未提供參數時會從 `8767` 開始，最多嘗試
100 個 Port，直到實際 bind 成功；接著等待 WebUI capabilities identity ready
後開啟瀏覽器。使用 `--port 9000` 可固定只嘗試一個 Port；使用
`--port 9000 --auto-port` 則會從 `9000` 開始自動搜尋。

詳細選項與工作流程請參閱 [CLI README](docs/cli/README.zh-TW.md) 和
[WebUI README](docs/webui/README.zh-TW.md)。

預設情況下，實機工作階段會透過 `pyvisa.ResourceManager()` 使用系統 VISA
執行階段。CLI 開啟 VISA 的指令可使用 `--visa-library "@py"` 選擇選用的
pyvisa-py 後端；WebUI 一律使用系統 VISA，且不提供後端選擇器。

## 建置

建置 wheel 與 source distribution。這會使用上面安裝的 `dev` extra 中的 `build` 套件：

```powershell
.\.venv\Scripts\python.exe -m build
```

這只會產生一個 Python 發行套件：

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

獨立執行檔採用 Windows 導向的 PyInstaller 工作流程。PyInstaller 已包含在
Windows `dev` 相依套件中，因此透過
`uv sync --all-extras --locked --link-mode=copy` 建立的開發環境已可用於發布
建置與正式發布驗收。

建置獨立的 CLI 和 WebUI 啟動器執行檔：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

預設情況下，這些命令會產生：

```text
dist\meters-tool.exe
dist\meters-tool-webui-launcher.exe
```

建置包含 wheel、sdist、獨立執行檔與檢查碼 (checksums) 的發佈資料夾：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

這會產生帶有版本號的發佈產物：

```text
release\<version>\meters-tool-<version>.exe
release\<version>\meters-tool-webui-launcher-<version>.exe
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

`release-acceptance.ps1` 是針對乾淨、已提交工作樹的正式無硬體發布驗收。
它會執行完整無硬體測試（包含 wrapper 測試）、呼叫一次
`build_release.ps1`，並驗證最終 wheel、source distribution、CLI 獨立 EXE、
WebUI Launcher 獨立 EXE 與 SHA-256 checksums；接著執行乾淨安裝套件 smoke
test、最小獨立執行檔 smoke test、指定 target 的 preflight 與既有的
PlanOnly 驗證。通過後會輸出可直接上傳至 GitHub Release 的版本化目錄。
最後的 `live-cli-check.ps1` 呼叫是 `-Suite minimal -PlanOnly -SkipPreflight`；
它只產生規劃，不會開啟 VISA 資源。每個 recorded command 會顯示
`[start]` 以及含執行時間的 `[passed]` 或 `[failed]`，詳細的 child-process
stdout/stderr 仍會保留在 acceptance run directory。完整 pytest 可能透過
wrapper contract tests 建立 `.tmp_tests\cli_live\...`；看到該目錄不代表正在
執行真實儀器測試。長時間的 PyInstaller build 不應被誤認為正在等待 external trigger。

## 測試

開發迭代時可先跑 focused tests：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

執行靜態檢查：

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

執行每日快速無硬體測試套件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py
```

Windows wrapper 合約的 CI 工作會另外執行
`tests\cli\test_cli_wrappers.py`。完整的 `release-acceptance.ps1` 門檻只應
在正式發布前執行。

如果 Windows 系統暫存目錄權限阻擋了 pytest，請改用 repository-local 暫存目錄重新執行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py --basetemp .tmp_tests\pytest_tmp
```

## Codex / Agent Skill

本專案提供選用的 Codex Skill 範本，供想要要求 Codex 或其他 agents
安全遵循 Meters CLI/worker 合約的使用者使用。安裝與使用方式請參考
[Codex Skill 範本](docs/skill/README.zh-TW.md)。

## 文件

* [Core README](docs/core/README.zh-TW.md)
* [支援型號](docs/core/supported-models.md)
* [CLI 使用者指南](docs/cli/USER_GUIDE.zh-TW.md)
* [CLI README](docs/cli/README.zh-TW.md)
* [WebUI README](docs/webui/README.zh-TW.md)
* [WebUI 使用者指南](docs/webui/USER_GUIDE.zh-TW.md)
* [Monorepo 架構](docs/architecture/monorepo-layout.md)
* [測試指南](docs/testing-guidelines.md)
* [貢獻指南](docs/CONTRIBUTING.md)
* [Codex Skill 範本](docs/skill/README.zh-TW.md)
* [公開合約](docs/contracts)
* [Meters CLI JSONL 合約](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker 合約](docs/contracts/meters-worker-contract.md)

## 貢獻

歡迎提交貢獻。在提交 pull request 之前，請閱讀 [貢獻指南](docs/CONTRIBUTING.md)。對儀器支援或實機行為的變更，在適用時需要提供實體儀器驗證證據。

## 授權條款與免責聲明

本專案採用 MIT License。詳見 [LICENSE](LICENSE)。

本專案是獨立且非官方的專案，未與 Keysight Technologies 建立從屬、背書或贊助關係。

使用者需自行遵守所有適用的 Keysight 軟體、driver、儀器與文件授權條款。
