# Codex 用量统计

一个本地 Codex token 用量统计工具。它会读取本机 Codex session 记录，提供网页仪表盘和轻量桌面版窗口，用于查看不同时间范围、项目、会话维度下的 token 消耗。

## 目的

写这个工具的主要目的，是给使用第三方中转站的人一个本地参照系：看看中转站账单里的倍率、消耗和自己本机记录到的 token 用量之间，有没有离谱到需要警觉的虚标。

它不是用来和官方统计一较高下的。官方额度、服务端计费、缓存折算、隐藏上下文、工具调用和滚动窗口，本来就可能和本地 session 文件的口径不完全一致。这个项目更像一个“差异放大镜”：当第三方账单看起来非常玄学时，至少可以多一个本地视角来判断问题是不是大到不正常。

## 功能

- 查看当天、本周、当月 token 消耗
- 统计输入、缓存输入、输出、推理输出、总计
- 查看 5 小时额度和一周额度剩余
- 查看最近一轮对话 token 消耗
- 查看项目维度用量，支持分页和每页条数调整
- 查看会话 ID 维度用量，支持分页和每页条数调整
- 页面每 5 秒自动刷新数据


## 文件结构

```text
codex_usage.py          本地 HTTP 服务和 Codex session 统计逻辑
codex_usage.html        前端页面
desktop.py              桌面版入口，启动本地服务并打开桌面窗口
assets/
  codex_usage_icon.ico  Windows 图标
  codex_usage_icon.icns macOS 图标
  codex_usage_icon.png  PNG 图标
```

## 安装依赖

建议使用 Python 3.10+。

```powershell
pip install pywebview pyinstaller
```

网页模式只依赖 Python 标准库；桌面版和打包需要 `pywebview`、`pyinstaller`。

## 网页模式运行

```powershell
python codex_usage.py
```

默认打开：

```text
http://127.0.0.1:8765
```

常用参数：

```powershell
python codex_usage.py --port 8766
python codex_usage.py --no-browser
python codex_usage.py --codex-home "C:\Users\你的用户名\.codex"
python codex_usage.py --frontend ".\codex_usage.html"
```

## 桌面模式运行

```powershell
python desktop.py
```

桌面模式会自动找空闲端口，在后台启动统计服务，然后打开一个应用窗口。

## 打包 Windows 桌面版

```powershell
pyinstaller --onefile --noconsole --name codex-usage-desktop --icon assets\codex_usage_icon.ico --add-data "codex_usage.html;." desktop.py
```

生成文件：

```text
dist\codex-usage-desktop.exe
```

运行：

```powershell
.\dist\codex-usage-desktop.exe
```

## 打包 macOS

需要在 macOS 上执行：

```bash
pyinstaller --onefile --windowed --name codex-usage-desktop --icon assets/codex_usage_icon.icns --add-data "codex_usage.html:." desktop.py
```

## 打包 Linux

需要在 Linux 上执行：

```bash
pyinstaller --onefile --windowed --name codex-usage-desktop --add-data "codex_usage.html:." desktop.py
```

## 常见问题

### 为什么用量和 Codex 自己显示的不完全一样？
本工具读取本地 session 文件；Codex 官方额度通常是服务端口径。隐藏系统提示词、工具调用、缓存折算、滚动窗口、本地文件缺失或归档都会造成差异。

## 声明

本项目诞生于一次高浓度 vibe coding：人类没有写代码，人类只是路过、皱眉、截图、画红框、说“这里怪怪的”。其余部分由 AI 在需求的雾里自行生长，偶尔坍缩，偶尔重构，最终长成了这个能跑的东西。

如果你在代码里看到了某种稳定的工程意志，那大概率不是我写的；如果你看到了反复横跳的产品审美和突如其来的需求变更，那确实是我来过。

还有，这个声明也是AI写的。🫡


## 许可证
MIT
