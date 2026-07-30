# Meters Tool Core

Core 包含供 CLI 與 WebUI 元件在支援的數位萬用電表整合中所使用的公開 API 與擷取執行階段合約。

Core 負責共享的請求模型、驗證、dry-run 規劃、執行階段工作階段協調、事件/結果類型、控制面介面、設定檔 metadata，以及 Meters Tool 擷取執行階段的安全規則。它會隨單一的 `meters-tool` 發行套件一同提供，同時保留 `meters_tool_core` 的 import 邊界。

Core 可以透過 `StartRequest` 與 `InstrumentConfig` 傳遞選用的 `visa_library` 值。當未設定時，live VISA 工作階段會使用 `pyvisa.ResourceManager()`，也就是系統預設的 VISA 執行階段。CLI 診斷可以傳入像 `@py` 這類值；WebUI 執行則會保持未設定。

目前支援範圍如下：

- 34461A：已驗證 USB/system VISA、LAN/system VISA，以及僅限 CLI、使用
  pyvisa-py `@py` 的 LAN/TCPIP。
- 34460A：目前已核准工作流程中的 USB/system VISA，包括明確提升的 DCV
  Ratio 範圍；LAN/TCPIP 範圍仍待驗證。

穩定的型號身份如下：

| 儀器 | 穩定型號 ID |
| --- | --- |
| `34461A` | `keysight-34461a` |
| `34460A` | `keysight-34460a` |

詳細身份與支援規則請參閱 [Core 整合](integration.md) 和
[支援的型號](supported-models.md)。

對 CLI/WebUI 啟動來說，`StartRequest.instrument_model = None` 代表對 live
資源進行自動偵測。配接器可先以只查 IDN 的 preflight 找出連接中的設定檔，
但該 preflight 不是最終的安全邊界。`run_start_session()` 會再次執行 Core
擁有的執行階段設定檔解析、請求驗證與最終支援政策閘門。除非 simulator
資源已可確定地命名型號，例如 `SIM::34460A` 或 `SIM::34461A`，否則 dry-run
與 simulator 啟動都必須使用明確的型號。

一般 CLI、WebUI 與 Core 啟動使用 Product mode，要求確切的範圍與請求功能
已對產品開放。僅限維護者使用的 Validation mode 只能執行明確註冊、尚待
驗證的傳輸或功能範圍以收集證據。通過驗證的產物不會自動提升公開支援。
Simulator 只提供確定性的合約與工作流程驗證，不代表實機量測準確度或硬體
支援。

CLI 與 WebUI 元件各自負責自己的命令列、網頁、包裝器與序列化層。Core 不得 import `meters_tool_cli` 或 `meters_tool_webui`。

## 驗證

無硬體 Core 驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

除了明確檢查元件邊界的測試之外，Core 驗證不應需要 import CLI 或 WebUI。

## 文件

- [Core 整合](integration.md)
- [支援的型號](supported-models.md)
- [變更日誌](../../CHANGELOG.md)
