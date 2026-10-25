# 新版飞书适配指南

升级后的偏移不可直接沿用。profile 以原 Framework SHA-256 和原指令做双重约束；任何一个不匹配都会拒绝修改。

## 1. 查看新版信息

在仓库根目录执行：

```bash
python3 -m feishu_patcher prepare-update --launch
# 在官方飞书内完成升级并退出它
python3 -m feishu_patcher inspect --app /Applications/Lark.app
```

记录版本、build、架构和 Framework SHA-256。`profile` 为 `null` 就是没有可安装的匹配项。版本号相同并不够：同一 `147.0.7727.149` 曾出现两个 Framework 哈希，旧偏移必须丢弃。

## 2. 生成候选 profile

```bash
python3 -m feishu_patcher adapt \
  --app /Applications/Lark.app \
  --output profiles/<version>-arm64.candidate.json
```

候选文件的 `reviewed` 固定为 `false`，安装器不会使用它。生成过程要求每个锚点恰好映射到一个函数入口；缺失或有歧义时会停止。

## 3. 审阅反汇编

对候选 profile 中的每个 `offset`，查看前后指令。Mach-O 本项目标下 `__text` 的地址与文件偏移通常一致，但仍应以 `otool -l` 为准。

```bash
BIN='/Applications/Lark.app/Contents/Frameworks/Lark Framework.framework/Versions/Current/Lark Framework'

objdump -d --arch=arm64 \
  --start-address=0xOFFSET_BEFORE \
  --stop-address=0xOFFSET_AFTER \
  "$BIN"
```

需要确认：

- 候选位置确实是函数开头，而不是函数内部的另一个栈调整。向后找到下一处 `sub sp, sp, #imm`，它应当落在候选入口之后一段完整函数体的位置，而不是紧挨着的几条指令。
- 原指令是 `sub sp, sp, #...`，随后有保存寄存器的 `stp` 函数序言。
- 把函数体内的 `ADRP + ADD` 解出来，确认引用的是对应锚点，而不仅是附近另一个字符串。Controller 入口应看到 `watermark_controller.cc`、`UpdateWatermarkView` 和 `can_create_watermark is false!`。Workspace 状态入口应看到 `close watermark_view`。定时检查入口应看到 `WebViewWorkspace::CheckWatermark`，以及创建或补回 `WatermarkView` 的日志。
- 三个候选分别覆盖 Controller 更新、Workspace 状态更新和定时检查。

当前这份 Framework 的 `__text` 虚拟地址和文件偏移都是 `0x4000`，因此 profile 里的文件偏移可以直接当作 `objdump --start-address`。换版本后仍要用 `otool -l` 核对，不能默认两者相等。

如果实现已重构，应更新 `ANCHORS` 和定位逻辑，不能为了通过校验而手工填写未经确认的偏移。

## 4. 批准 profile

将候选文件改成正式文件名，然后明确确认已经完成反汇编检查：

```bash
mv profiles/<version>-arm64.candidate.json profiles/<version>-arm64.json
python3 -m feishu_patcher approve \
  profiles/<version>-arm64.json \
  --i-reviewed-disassembly
```

## 5. 安装和验证

日常使用：

```bash
python3 -m feishu_patcher refresh --launch --stop
```

`refresh` 在安装和验证后会恢复日常桌面配置：开机启动补丁版，并把官方升级源收纳到 `~/Library/Application Support/FeishuNoWatermark/Official/Source`。该目录不带应用扩展名，且不会进入 Spotlight 索引。下一次升级时再次执行 `prepare-update --launch`，它会自动将官方 App 恢复到 `/Applications/Lark.app`。

只做对照、需要官方 App 留在 `/Applications/Lark.app` 时，改用：

```bash
python3 -m feishu_patcher install --source /Applications/Lark.app --destination /Applications/飞书.app
python3 -m feishu_patcher verify --app /Applications/飞书.app
```

不要加 `--launch`，也不要接着执行 `desktop`。两份 App 共用 `~/Library/Application Support/LarkShell` 的 `SingletonLock`，官方进程还在时启动补丁版不会加载补丁后的二进制。先完全退出官方飞书，再打开 `/Applications/飞书.app`。

登录后检查主窗口、独立聊天窗口、文档窗口和弹窗。可选的 AX 检查：

```bash
swiftc tools/WatermarkWindowCheck.swift -o /tmp/WatermarkWindowCheck
PID=$(pgrep -f '/Applications/飞书\.app/Contents/MacOS/Feishu' | head -1)
/tmp/WatermarkWindowCheck "$PID"
```

主进程的命令行会把可执行文件路径重复一遍，所以不要用以 `$` 结尾的整行匹配，否则 `pgrep` 会漏掉正在运行的飞书。这个工具需要运行它的终端具有“辅助功能”权限。

## 6. 提交适配

提交内容至少包括：

- 新 profile。
- `inspect` 输出中的版本、build 和 SHA-256。
- 三处反汇编审核结论。
- 登录主窗口和其他常用窗口的验证结果。
- 如果锚点或控制流变化，对扫描器及文档的同步更新。
