# 支援型號

本文件說明 Meters Tool 使用者目前可用的 Product-open 支援範圍。
它是支援型號、連線、backend、量測、觸發與重要限制的共用使用者參考文件。

## 型號設定檔

Meters Tool 目前支援以下儀器型號：

| Model ID | Instrument | Reading memory | Current max | External trigger |
| --- | --- | ---: | ---: | --- |
| `keysight-34461a` | Keysight 34461A | 10000 | 10 A with 10A terminal | supported |
| `keysight-34460a` | Keysight 34460A | 1000 | 3 A | Not supported in base scope |

CLI 與 WebUI 的 live 執行在未指定 model 時，會依連接儀器身分偵測 34460A/34461A。
明確選擇 model 只是 expected-model check：不一致時會在設定前失敗，不會解鎖其他支援範圍。
Dry-run 與 simulation 可使用所選的 planning model。

## 精確範圍實機支援

live Product 支援採精確範圍制。Meters 目前提供一個獨立支援的 Product workflow，`start-trigger-record`。
只有在偵測到的 model、workflow、精確 transport/backend 連線範圍、量測與觸發模式同時受支援時，live 執行才是 Product-open。
支援不會在 USB/system-VISA、TCPIP/system-VISA 與 TCPIP/pyvisa-py 之間轉移。
硬性 model/profile 限制仍會強制執行。

不在目前 Product-open matrix 內的要求，包括未知 model、不支援的連線或功能組合，以及硬性安全限制，都會 fail closed。

在 live 模式中，CLI `--model` 與 WebUI `Expected model` 只是 expected-model guard。
runtime driver/profile 由連接儀器 `*IDN?` 決定。selected/detected 不一致會在儀器設定前失敗。
Dry-run 與 simulator 執行使用 selected/no-hardware planning profile，不查詢實機。

| Capability / workflow | 34461A | 34460A |
| --- | --- | --- |
| Immediate DC/AC voltage/current | Open | Open on USB/system-VISA |
| 2W/4W resistance | Open | Open on USB/system-VISA |
| Software trigger/timer | Open | Open on USB/system-VISA |
| Custom buffered workflows | Open | Open, limited by 1000-reading memory |
| Frequency | Open | Open on USB/system-VISA |
| Period | Open, no Period timeout option | Open, no Period timeout option |
| External simple/custom | Open | Not open in base 34460A profile |
| DCV Ratio | Open | Open only on USB/system-VISA |
| 10 A / current-terminal | Open with operator-confirmed wiring | Not supported |
| Buffer drain above profile memory | Up to 10000 readings | Not supported above 1000 |
| LAN/TCPIP with system VISA | Open for 34461A | Not currently supported |
| LAN/TCPIP with pyvisa-py `@py` | Open for optional CLI-only 34461A scope | Not currently supported |

### 精確範圍詳細資訊

- **接線安全與 10 A 路徑**：選擇 10 A current terminal 需要操作人員手動確認實體導線接線，以避免硬體損壞。
- **讀值記憶體限制**：34461A custom runs 超過 10,000 readings、34460A custom runs 超過 1,000 readings 時，都需要明確確認 overflow-risk。
- **Fail-Closed Policy**：上方 matrix 中未明確標示為 open 的任何 model、transport、backend、量測或觸發組合，均為未支援並 fail closed。

## VISA Backend 支援

VISA backend 支援是精確連線範圍的一部分，而不是 model capability。
除非介面明確提供另一個受支援 backend，正常 Product 作業使用電腦的 System VISA runtime。
選用 backend scopes 互相獨立：選擇另一個 backend 不會解鎖未支援的 model、transport、量測或其他 Product 支援。
WebUI 不提供 backend selector。

## 量測能力

34460A 與 34461A profiles 目前提供相同的量測名稱，順序如下：

每個受支援量測都有下表列出的 model-specific 範圍與限制。

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `frequency`
- `period`
- `resistance-2w`
- `resistance-4w`

| Measurement | 34461A range choices | 34460A range choices | NPLC choices | AC filter | Gate time | Frequency timeout | Current terminal | DCV input Z | Auto Zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `current-dc` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | 0.02, 0.2, 1, 10, 100 | none | none | none | 34461A: 3, 10; 34460A: none | none | on, off, once |
| `voltage-dc` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on, off, once |
| `voltage-dc-ratio` | 0.1, 1, 10, 100, 1000 V | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on/default only |
| `current-ac` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | none | 3, 20, 200 Hz | none | none | 34461A: 3, 10; 34460A: none | none | none |
| `voltage-ac` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz | none | none | none | none | none |
| `frequency` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | auto, 1s; default auto | none | none | none |
| `period` | 0.1, 1, 10, 100, 750 V | same as 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | none | none | none | none |
| `resistance-2w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | on, off, once |
| `resistance-4w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | same as 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | none |


Auto Zero supports on, off, and once for current-dc, voltage-dc, and resistance-2w. voltage-dc-ratio accepts only the default/on Auto Zero request state.
AC, Frequency, and Period measurements do not use NPLC or Auto Zero. Resistance 4-wire rejects the once Auto Zero choice.

DCV input impedance is available for voltage-dc and voltage-dc-ratio. Allowed values are default, 10m, and auto; default preserves the current configured instrument state.

AC bandwidth/filter selection is available for `current-ac`, `voltage-ac`, `frequency`, and `period`. Allowed values are `3`, `20`, and `200` Hz.
Leaving the field unset preserves the existing AC current/voltage behavior. Frequency and Period instead apply the effective default `20` Hz filter.

Frequency and Period use voltage range choices of `0.1`, `1`, `10`, `100`, and `750` V. Auto Range is the default.
Gate time accepts `0.01`, `0.1`, or `1.0` seconds and defaults to `0.1`.
Frequency timeout accepts `auto` or `1s` and defaults to `auto`. Period does not expose a timeout option. Explicit Period timeout values are rejected.

DCV Ratio readings use unit `ratio`. Frequency readings use `Hz`, and Period readings use `s`.

Current terminal selection is available only for the 34461A current profiles.
Selecting the 10 A range requires the 10 A terminal, and selecting the 10 A terminal with a manual range requires the 10 A range.
Operators must confirm the range, terminal, and physical lead wiring to prevent hardware damage.
The 34460A current profiles support up to 3 A only and do not expose a 34461A-style 10 A terminal path.

## 觸發能力

The 34461A supports:

- software
- software timer
- external
- immediate
- immediate-custom
- software-custom
- external-custom

The 34460A base scope supports:

- software
- software timer
- immediate
- immediate-custom
- software-custom

The 34460A base scope does not support external trigger modes because LAN/LXI/external trigger capability is optional on that model.

## 讀值記憶體

Custom runs compare the requested reading count with the model reading-memory limit.

- 34461A custom runs above 10000 readings require explicit overflow-risk acknowledgement.
- 34460A custom runs above 1000 readings require explicit overflow-risk acknowledgement.
- Buffer drain remains capped at the model reading-memory limit and is not relaxed by that acknowledgement.

## 未支援範圍

Models not listed in this document are not currently supported in Product mode.
A model, connection/backend, measurement, trigger mode, or workflow combination not listed as Product-open is unsupported.
Unsupported combinations are rejected rather than implicitly enabled.
