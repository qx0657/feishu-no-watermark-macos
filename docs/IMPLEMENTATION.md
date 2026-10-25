# 147.0.7727.149 实现记录

## 观察结果

测试环境为 Apple Silicon Mac，飞书 `147.0.7727.149`，Framework 位于：

```text
/Applications/Lark.app/Contents/Frameworks/
  Lark Framework.framework/Versions/147.0.7727.149/Lark Framework
```

辅助功能树显示独立的 `WatermarkWidget` 和 `WatermarkContentView`。Framework 字符串中同时存在：

```text
watermark_controller.cc
WatermarkController
UpdateWatermarkView
can_create_watermark is false!
webview_workspace.cc
close watermark_view
StartWatermarkCheckTimer
CheckWatermark
```

这说明主窗口水印由原生 Views 层维护，并有定时检查与重新创建逻辑。

## 排除过的方案

### 网页 CSS

用户脚本适合网页版 DOM；客户端水印来自原生窗口层，所以 CSS 不能覆盖。

### Remote Feature 配置

本地配置中能看到 `lark.pc.core.use_watermark_check_disabled` 和 `lark.pc.enable.watermark_no_window`，但修改后会被远端配置恢复，而且在隔离写保护测试中也没有关闭当前租户的水印。

### 辅助功能和 WindowServer

`WatermarkWidget` 的辅助功能窗口位置可写，但移动它没有改变实际绘制。对候选窗口调用私有 WindowServer alpha API 也没有影响实际屏幕截图，说明不能把它当成普通透明覆盖窗稳定隐藏。

## 二进制定位

Mach-O 的 `__cstring` 中包含上述日志字符串。扫描器执行以下步骤：

1. 通过 `otool -l` 得到 `__text` 与 `__cstring` 的虚拟地址、文件偏移和大小。
2. 找到锚点字符串的文件偏移并换算为虚拟地址。
3. 在 `__text` 扫描 ARM64 `ADR` 或 `ADRP + ADD (immediate)` 引用。
4. 从引用位置向前寻找最近的 `sub sp, sp, #imm` 函数序言。
5. 保存函数文件偏移、原 4 字节指令和上下文。

`c0035fd6` 是 ARM64 小端编码的 `ret`。只拦截 Controller 入口仍会由 Workspace 创建水印；三个入口同时变成 `ret` 后，旧二进制重启时不再创建 `WatermarkWidget`，定时检查也不会恢复它。

### 已实机验证的 Framework

SHA-256：`6c5e1c37c7284087060933f3a1b2af0c33f7a3335c0e1a920499d9188316a8a9`。

| 文件偏移 | 原指令 | 解码 | 作用 |
| --- | --- | --- | --- |
| `0x46f24f8` | `ff0306d1` | `sub sp, sp, #0x180` | Controller 更新入口 |
| `0x4724a48` | `ff4306d1` | `sub sp, sp, #0x190` | Workspace 水印状态更新 |
| `0x472be70` | `ffc305d1` | `sub sp, sp, #0x170` | Workspace 定时自愈检查 |

后两个入口相距 `0x7428`。这份 profile 已被下面的同版本重建替换，仓库里不再保留可直接安装的旧偏移。

### 2026-10-25 的同版本重建

本机 `/Applications/Lark.app` 的版本号和 build 没变，Framework SHA-256 变为 `9b2c081b8e3eb35364fb744342e43a9836784571153c32392143a089e7b33981`。`__text` 的虚拟地址和文件偏移都是 `0x4000`。三个锚点仍然各只出现一次，并且各自只回溯到一个函数入口。序言指令没变；Controller 入口后移 `0x102bb4`，两个 Workspace 入口后移 `0x102c4c`，二者间距仍是 `0x7428`。

| 文件偏移 | 原指令 | 下一处序言 | 作用 |
| --- | --- | --- | --- |
| `0x47f50ac` | `ff0306d1` | `0x47f553c` | `WatermarkController::UpdateWatermarkView` |
| `0x4827694` | `ff4306d1` | `0x4827cb0` | `WebViewWorkspace::UpdateWatermarkView` |
| `0x482eabc` | `ffc305d1` | `0x482efa4` | `WebViewWorkspace::CheckWatermark` |

函数体内的字符串引用：

- `0x47f50ac`：`watermark_controller.cc`、`WatermarkController::UpdateWatermarkView`、`can_create_watermark is false!`（引用点 `0x47f5188`）、`create watermark content view, uid:`。
- `0x4827694`：`WebViewWorkspace::UpdateWatermarkView`、`close watermark_view`（引用点 `0x482772c`、`0x4827744`）、`has_watermark_:`、`IsWatermarkEnabled:`、`WatermarkView is nullptr`、`WatermarkView created:`。
- `0x482eabc`：`WebViewWorkspace::CheckWatermark`（引用点 `0x482ebb8`、`0x482ec64`、`0x482ed08`、`0x482eed4`）、`WatermarkView is nullptr!`、`WatermarkView created:`。

这三处都是 `sub sp` 后紧跟保存寄存器的 `stp`，下一处栈分配远在函数体之后。当前 profile 使用这组偏移。

## 签名与登录态

修改嵌套 Framework 会破坏官方签名。安装器对副本执行：

```bash
codesign --force --deep --sign - /Applications/飞书.app
codesign --verify --deep --strict /Applications/飞书.app
```

`--sign -` 生成 ad-hoc 本机签名。官方 App 的钥匙串 ACL 不会自动信任这个新代码身份，所以 macOS 可能要求用户用登录密码授权。在 `6c5e1c37…` 上选择“始终允许”后，已有飞书登录态可以继续使用。`9b2c081b…` 的代码身份同样变了，预期还会再授权一次，这次还没有复测登录态。

## 验证标准

1. 三个补丁位置的字节是 `c0035fd6`，反汇编为 `ret`。
2. `codesign --verify --deep --strict` 成功。
3. 登录后的飞书主窗口实际屏幕截图无姓名/工号平铺水印。
4. 辅助功能树不再出现标题为 `WatermarkWidget` 的窗口。
5. 原 `/Applications/Lark.app` 的 Framework 在三个补丁偏移处仍是原来的 `sub sp` 指令。

`6c5e1c37…` 完成了全部五项。`9b2c081b…` 在 2026-10-25 完成了反汇编审核、副本三处 `ret` 写入、签名验证，并确认官方 Framework 的对应字节未被修改。补丁副本装在 `/Applications/飞书.app`。当时官方进程仍在运行，两份 App 不能同时占用 `LarkShell`，所以这份新哈希还没有复测登录后截图和辅助功能树。
