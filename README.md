# 飞书 Mac 客户端无水印研究工具

这个项目记录并工程化了 macOS 官方飞书客户端水印窗口的定位、补丁、验证和版本升级适配流程。安装器始终复制官方 App，再修改副本；默认生成 `/Applications/飞书.app`，不会覆盖 `/Applications/Lark.app`。

> 本项目仅用于技术学习、逆向分析和个人测试。水印可能是组织的数据安全策略。使用前请确认你有权修改本机软件，并遵守所在组织的安全规定、保密义务、软件许可和适用法律。不要用它规避审计、泄露内部资料或处理你无权访问的数据。项目与飞书、Lark、字节跳动及参考项目作者无隶属关系。

## 当前支持

| 平台 | 飞书版本 | 架构 | Framework SHA-256 | 状态 |
| --- | --- | --- | --- | --- |
| macOS | `147.0.7727.149`（build `7727.149`） | Apple Silicon `arm64` | `9b2c081b8e3eb35364fb744342e43a9836784571153c32392143a089e7b33981` | 已审核偏移并完成补丁与签名验证 |
| macOS | `147.0.7727.149`（build `7727.149`） | Apple Silicon `arm64` | `6c5e1c37c7284087060933f3a1b2af0c33f7a3335c0e1a920499d9188316a8a9` | 旧二进制，已实机验证；profile 已替换 |

同一版本号可以对应不同的 Framework。安装器只认版本、架构、原始 SHA-256 和原指令都匹配的 profile。当前 profile 绑定上面第一行的哈希。

上一份哈希做过这些实机检查：登录态恢复、主窗口截图无姓名/工号水印、辅助功能树不再出现 `WatermarkWidget`、补丁副本通过 `codesign --verify --deep --strict`。当前哈希已核对三处反汇编、写入 `ret`，并通过同样的签名检查；登录后的窗口对照还没有在这份二进制上复测。

## 快速使用

要求：macOS、Python 3、Xcode Command Line Tools，以及安装在 `/Applications/Lark.app` 的官方飞书。以下命令在仓库根目录执行。

```bash
# 查看版本、架构、Framework 哈希和匹配的 profile
python3 -m feishu_patcher inspect

# 复制官方 App、应用补丁、本机签名并启动
python3 -m feishu_patcher install --launch --stop

# 检查补丁字节和签名
python3 -m feishu_patcher verify

# 让开机登录项指向补丁版，并隐藏官方升级源，避免启动台出现两个飞书
python3 -m feishu_patcher desktop
```

首次启动补丁版时，macOS 可能询问是否允许“飞书”访问钥匙串中的既有密钥。输入 Mac 登录密码并选择“始终允许”后，原登录状态通常可以继续使用。原因是修改后的 App 必须重新签名，本机签名与官方签名不是同一身份。

日常从“应用程序”打开 **飞书.app**。它在 Finder、Dock 和菜单栏中均显示为“飞书”。执行 `desktop` 后，开机登录项会改为 `/Applications/飞书.app`；官方原版会收纳到 `~/Library/Application Support/FeishuNoWatermark/Official/Source`，其 `Info.plist` 在保存状态下也会临时改名。该目录没有应用扩展名并被排除在 Spotlight 索引之外，因此新版 macOS“App”界面不会把升级源显示成第二个飞书；恢复升级时会自动还原完整 App 结构。

## 工作原理

当前客户端不是把全屏水印作为普通网页 CSS 绘制。飞书的 AHA/Chromium Framework 会创建原生 `WatermarkWidget` / `WatermarkContentView`，并由 `WatermarkController` 和 `WebViewWorkspace` 管理。只注入用户脚本、修改网页样式或调整辅助功能窗口位置，都不能稳定影响最终渲染。

本项目对三个创建或自愈入口做最小 ARM64 补丁：把函数入口的栈分配指令替换为 `ret`。

1. `WatermarkController::UpdateWatermarkView`
2. `WebViewWorkspace` 的水印状态更新入口
3. `WebViewWorkspace::CheckWatermark`

每个 profile 同时记录飞书版本、原始 Framework SHA-256、文件偏移和原指令。只有版本、架构、哈希和原字节全部匹配时才允许安装，从而避免把旧偏移写入新版二进制。

## 飞书升级后怎么办

补丁版可能被客户端升级器覆盖。推荐临时显示并启动官方 `/Applications/Lark.app` 完成升级，再从它重新生成补丁副本：

```bash
python3 -m feishu_patcher prepare-update --launch
# 在官方飞书内完成升级并退出它
python3 -m feishu_patcher inspect
python3 -m feishu_patcher refresh --launch --stop
```

如果新版已有 profile，`refresh` 会覆盖安装、验证签名与补丁、恢复补丁版登录项，并再次收纳官方升级源。旧补丁版备份会移到 `~/Library/Application Support/FeishuNoWatermark/Backups`，不会在启动台生成额外图标。

如果提示 `no exact profile`，说明二进制已经变化。版本号可以不变，只换 Framework 哈希，旧偏移也不能沿用。请按 [新版适配指南](docs/ADAPTING.md) 生成候选 profile、审阅反汇编，再批准并安装。扫描器以稳定的日志字符串为锚点，重新解析 ARM64 `ADR/ADRP + ADD` 引用并回溯函数序言，所以通常不需要人工从整份 280 MB 以上的 Framework 中盲找偏移。

## 和官方客户端对照

`install` 只复制并修补 `/Applications/飞书.app`，不移动官方 App，也不改开机登录项。需要保留官方窗口作对照时用它，不要用 `desktop` 或 `refresh`；后两个命令会把官方升级源收纳起来。

两份 App 的 bundle id 都是 `com.electron.lark`，用户数据都在 `~/Library/Application Support/LarkShell`。该目录里的 Chromium `SingletonLock` 保证同时只有一个实例。官方进程还在时打开补丁版，启动请求会交回官方进程，看到的仍是未补丁的画面。

中文系统里两份 App 的显示名都是「飞书」。用路径区分：`/Applications/Lark.app` 是官方，`/Applications/飞书.app` 是补丁版。

对照步骤：先看官方窗口，完全退出飞书，再打开补丁版。首次启动补丁版时按上面的方式处理钥匙串授权。看完后退出补丁版，重新打开官方 App，即可回到带水印的客户端。

## 网页版方案

网页版不需要修改客户端二进制。参考项目 [lbb00/remove-feishu-watermark](https://github.com/lbb00/remove-feishu-watermark) 使用 Userscript 管理器在 `document-start` 注入 CSS，将常见水印节点的 `background-image` 设为 `none`。它覆盖飞书文档、工作台和 Web 聊天等页面，核心选择器包括 `[class*="watermark"]`、`.ssrWaterMark`、`#watermark-cache-container` 等。

Safari 可以使用 Userscripts 一类扩展加载该脚本；Chrome/Firefox 可以使用支持 Userscript 的扩展。网页方案只影响浏览器 DOM，无法处理当前 Mac 客户端的原生水印窗口，因此本项目采用独立的二进制补丁流程。

## 项目结构

```text
feishu_patcher/       CLI、Mach-O 元数据读取、ARM64 引用扫描与补丁逻辑
profiles/             按版本审核过的补丁 profile
docs/                 本次研究记录和新版适配步骤
tools/                可选的辅助功能窗口验证工具
tests/                ARM64 解码和定位算法测试
```

## 回退

退出补丁版，重新打开官方 `/Applications/Lark.app` 即可。安装器从不修改官方 App。需要清理补丁副本时，可在确认不再需要后手动移除 `/Applications/飞书.app` 及时间戳备份。

## 限制

- 当前只验证了 Apple Silicon；Intel 需要单独实现 x86_64 定位与补丁。
- 本机签名会改变代码身份，首次使用或重新适配后可能再次出现钥匙串授权。
- 飞书升级可能重构水印实现。候选 profile 必须检查反汇编，不能只相信自动扫描结果。
- 该方法只改变本机视觉层，不修改组织后台策略，也不影响文件导出、截图或复制流程中可能存在的其他水印机制。

## 许可证

代码使用 [MIT License](LICENSE)。参考项目采用其自己的许可证，本仓库不复制其源码。
