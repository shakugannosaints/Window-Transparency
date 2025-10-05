# 窗口透明度管理工具

一个运行于 Windows 11 的桌面小工具，可为任意顶层窗口设置专属透明度，并在下次启动时自动记忆已配置的窗口。

## 功能概览

- 枚举当前所有可见窗口（排除本工具自身）。
- 为选中的窗口设置 0-255 的透明度（0 为完全透明，255 为完全不透明）。
- 为不同窗口分别保存透明度设置，下次运行时自动应用。
- 支持鼠标悬停与离开两种透明度，可按需开启切换。
- 支持恢复默认透明度并移除记忆。

## 运行环境

- Windows 11
- Python 3.10 及以上（内置 `tkinter` 和 `ctypes`）

运行应用本身仅依赖 Python 标准库，无需额外第三方包。如需打包为独立可执行文件，请参考下文的“编译为可执行文件”。

## 快速开始

1. 安装 Python 3.10+，确保可在命令行执行。
2. 克隆或下载本项目至本地。
3. 在项目根目录执行：

```powershell
python main.py
```

启动后点击“选择窗口”，挑选一个正在运行的窗口，拖动“默认透明度”滑块调节并点击“应用透明度”。
如需在鼠标悬停时使用不同透明度，可勾选“启用鼠标悬停独立透明度”后设置对应滑块。

## 配置存储

透明度配置默认保存在：

```
%APPDATA%\WindowTransparencyManager\settings.json
```

你可以删除该文件以清空全部记忆。

## 测试

本项目提供了针对持久化逻辑的单元测试：

```powershell
python -m unittest discover -s tests
```

## 编译为可执行文件

项目内置了一个使用 PyInstaller 的打包脚本，可在 Windows 上生成单独的 `.exe` 文件。

1. 安装打包依赖：

	```powershell
	pip install -r requirements-build.txt
	```

2. 运行打包脚本（默认输出位于 `dist/WindowTransparencyManager.exe`）：

	```powershell
	python scripts\build_exe.py
	```

3. 如需仅清理构建产物，可执行：

	```powershell
	python scripts\build_exe.py --clean-only
	```

GitHub Actions 工作流会在每次提交或 PR 上自动执行测试与打包，并将 `WindowTransparencyManager.exe` 作为构建工件上传，可在仓库的 Actions 页面下载。若向仓库推送形如 `v*` 的标签（例如 `v1.0.0`），工作流还会自动创建 GitHub Release 并附带最新的可执行文件。

## 常见问题

- **调整后窗口立刻消失怎么办？** 将透明度设为 0 时窗口几乎不可见，可通过任务栏恢复焦点后重新设置透明度。
- **窗口标题变化导致未应用记忆？** 配置键包含窗口标题，当窗口标题发生改变时需要重新设置一次透明度。
