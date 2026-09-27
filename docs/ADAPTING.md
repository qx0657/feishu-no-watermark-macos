# 新版飞书适配指南

升级后的偏移不可直接沿用。profile 以原 Framework SHA-256 和原指令做双重约束；任何一个不匹配都会拒绝修改。

## 1. 查看新版信息

```bash
cd /Users/glow/dev/projects/github/feishu-no-watermark-macos
python3 -m feishu_patcher inspect --app /Applications/Lark.app
```

记录版本、build、架构和 Framework SHA-256。

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

- 候选位置确实是函数开头，而不是函数内部的另一个栈调整。
- 原指令是 `sub sp, sp, #...`，随后有保存寄存器的函数序言。
- 函数体引用对应锚点日志，并包含创建、刷新或检查水印的控制流。
- 三个候选分别覆盖 Controller 更新、Workspace 状态更新和定时检查。

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

```bash
python3 -m feishu_patcher install --launch --stop
python3 -m feishu_patcher verify
```

登录后检查主窗口、独立聊天窗口、文档窗口和弹窗。可选的 AX 检查：

```bash
swiftc tools/WatermarkWindowCheck.swift -o /tmp/WatermarkWindowCheck
PID=$(pgrep -f '^/Applications/飞书无水印.app/Contents/MacOS/Feishu$' | head -1)
/tmp/WatermarkWindowCheck "$PID"
```

这个工具需要运行它的终端具有“辅助功能”权限。

## 6. 提交适配

提交内容至少包括：

- 新 profile。
- `inspect` 输出中的版本、build 和 SHA-256。
- 三处反汇编审核结论。
- 登录主窗口和其他常用窗口的验证结果。
- 如果锚点或控制流变化，对扫描器及文档的同步更新。
