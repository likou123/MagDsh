# MagDsh

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**MagDsh** 是一个 Windows 桌面启动器：一次点击，先让 **Magpie** 在托盘后台运行，再启动 **DeepSeek Harness (DSH)** 并把 DSH 带到前台。

Magpie 是一个本地 AI 模型路由网关：让 Codex、Claude Code、Gemini CLI、DeepSeek Harness 等 Agent 统一接入 DeepSeek、Kimi、GLM、Claude、OpenAI 等模型供应商。它不是窗口缩放工具。

![MagDsh 软件位置界面](source/shots/settings-optimized.png)

## 功能

- **Magpie 托盘启动**：使用 Magpie 官方 `magpie tray` 命令，只驻留托盘，不弹出主界面。
- **DSH 前台启动**：等待 DSH 窗口出现后恢复并激活，避免启动器关闭后焦点回到 Magpie。
- **自动检测**：识别 Magpie 安装目录和 DSH 安装目录；任一缺失时弹出“软件位置”窗口。
- **路径持久化**：选择结果保存到 `%LOCALAPPDATA%\MagDsh\settings.ini`，下次直接使用。
- **避免重复启动**：Magpie 通过 `127.0.0.1:3425` 检测，DSH 通过进程快照检测；已在运行时不会重复拉起。
- **不请求管理员权限**：以当前用户权限运行，不弹 UAC。
- **UI 尺寸对齐**：在 125% 等 Windows 缩放下保持固定物理尺寸，启动窗口 500×342，软件位置窗口 700×512。
- **单文件分发**：PyInstaller 打包，无控制台窗口，运行时不联网、不写注册表。

## 快速开始

### 下载

Windows x64 单文件版本发布在 [GitHub Releases](https://github.com/likou123/MagDsh/releases/latest)。

下载 `MagDsh.exe` 后直接运行即可，不需要安装 Python。

### 直接运行

```text
MagDsh.exe
```

把 `MagDsh.exe` 放在任意目录即可。它会自动寻找默认安装位置：

- Magpie：`%LOCALAPPDATA%\Programs\magpie`
- DeepSeek Harness：`%LOCALAPPDATA%\Programs\DeepSeek Harness`

如果路径不同，启动时会弹出“软件位置”窗口，选择两个文件夹后保存即可。

### 命令行参数

| 参数 | 作用 |
|---|---|
| 无参数 | 自动检测并启动 |
| `--settings` / `-s` | 强制打开软件位置窗口 |
| `--help` / `/?` | 显示帮助 |

## 从源码构建

要求：

- Windows 10/11 x64
- Python 3.11+
- PowerShell 5.1+

```powershell
cd source\build
python -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建脚本会：

1. 使用 `source\.venv` 中的 Python 和 PyInstaller；
2. 生成 `source\build\MagDsh.exe`；
3. 复制到项目根目录 `MagDsh.exe`。

## 目录结构

```text
MagDsh/
├─ README.md
├─ LICENSE
├─ third_party_notices.md
├─ MagDsh.exe                 本地构建产物（不提交到 Git）
└─ source/
   ├─ build/
   │  ├─ build.ps1
   │  ├─ requirements.txt
   │  ├─ run_magdsh.py
   │  └─ MagDsh.exe
   ├─ src/magdsh/
   │  ├─ __main__.py
   │  ├─ appinfo.py
   │  ├─ launcher_form.py
   │  ├─ settings_form.py
   │  ├─ widgets.py
   │  ├─ theme.py
   │  ├─ dialogs.py
   │  └─ assets/
   ├─ shots/
   └─ 图标/
```

## 配置与日志

| 内容 | 位置 |
|---|---|
| 配置 | `%LOCALAPPDATA%\MagDsh\settings.ini` |
| 主日志 | `%LOCALAPPDATA%\MagDsh\MagDsh.log` |
| 启动追踪 | `%LOCALAPPDATA%\MagDsh\startup.log` |

## 工作方式

1. 解析 Magpie 和 DSH 的可执行文件路径；
2. 使用 `subprocess.Popen` 以各自安装目录为工作目录启动 Magpie；
3. Magpie 参数为 `tray`，不显示主窗口；
4. 延迟启动 DSH；
5. 通过 Win32 `ShowWindowAsync` / `SetForegroundWindow` 将 DSH 恢复到前台；
6. 启动器自动关闭。

启动器不会修改 Magpie 或 DSH 的安装文件，也不会自动提权。

## 注意事项

- **SmartScreen**：未签名的新构建第一次运行可能提示“未知发布者”。选择“更多信息 → 仍要运行”即可；如果重新构建，哈希变化后会重新提示。
- **Magpie 和 DSH 不是本项目的一部分**，需要单独安装。它们的许可证、更新和配置由各自项目负责。
- 本项目只负责“启动”和“路径选择”，不代理模型请求，也不保存 API Key。

## 许可证

本项目使用 [MIT License](LICENSE) 开源。

第三方依赖和运行时组件的许可证见 [third_party_notices.md](third_party_notices.md)。
