# Changelog

## 1.1.1 — 2026-11-13

### 新增

- 自动发现更多 Magpie / DeepSeek Harness 安装方式：
  - 默认安装目录；
  - Magpie 自定义安装目录（`HKCU\Software\magpie\InstallLocation`）；
  - 系统级 `Program Files` 安装；
  - Windows 卸载注册表中的 `InstallLocation` 和 `DisplayIcon`；
  - `App Paths` 注册表；
  - 当前正在运行的 Magpie / DSH 进程路径（适用于便携版和手动移动的目录）；
  - `PATH`（包括 `magpie.com` shim）；
  - Scoop、winget、Chocolatey 的包目录。
- 支持选择安装目录的上级目录，搜索深度增加到 3 层。
- 在 `startup.log` 中记录每次路径发现来源，便于排查。
- 完全未知的便携版目录仍可通过“软件位置”窗口手动选择并记住。

### 调整

- README 增加安装方式说明和更新日志入口。
- README 使用应用图标作为顶部品牌图。

## 1.1.0 — 2026-11-13

- 首个公开版本。
- Magpie 使用 `tray` 模式启动，只驻留托盘。
- DSH 启动后恢复到前台。
- 支持自动检测、路径持久化、无管理员权限运行。
- 提供 Windows x64 单文件 Release。
