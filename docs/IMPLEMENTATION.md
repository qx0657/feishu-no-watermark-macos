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

本版本确认的三个入口：

| 文件偏移 | 原指令 | 补丁 | 作用 |
| --- | --- | --- | --- |
| `0x46f24f8` | `ff0306d1` | `c0035fd6` | Controller 更新入口 |
| `0x4724a48` | `ff4306d1` | `c0035fd6` | Workspace 水印状态更新 |
| `0x472be70` | `ffc305d1` | `c0035fd6` | Workspace 定时自愈检查 |

`c0035fd6` 是 ARM64 小端编码的 `ret`。只拦截 Controller 入口仍会由 Workspace 创建水印；三个入口同时处理后，重启时不再创建 `WatermarkWidget`，定时检查也不会恢复它。

## 签名与登录态

修改嵌套 Framework 会破坏官方签名。安装器对副本执行：

```bash
codesign --force --deep --sign - /Applications/飞书.app
codesign --verify --deep --strict /Applications/飞书.app
```

`--sign -` 生成 ad-hoc 本机签名。官方 App 的钥匙串 ACL 不会自动信任这个新代码身份，所以 macOS 可能要求用户用登录密码授权。选择“始终允许”后，本次实测能够恢复已有飞书登录态。

## 验证标准

1. 三个补丁位置反汇编为 `ret`。
2. `codesign --verify --deep --strict` 成功。
3. 登录后的飞书主窗口实际屏幕截图无姓名/工号平铺水印。
4. 辅助功能树不再出现标题为 `WatermarkWidget` 的窗口。
5. 原 `/Applications/Lark.app` 的 Framework SHA-256 保持不变。
