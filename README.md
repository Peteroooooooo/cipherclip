[English](README.en.md)

# CipherClip

一个 Windows 剪贴板历史工具，基于 Python、pywebview、pystray、React 和 Vite 构建。

## 功能与使用

### 快速上手

- 把光标停在聊天框、输入框或编辑器里，按 `Alt + Space` 打开面板
- 用方向键或鼠标选择一条历史记录，按 `Enter` 会自动回到原输入位置并粘贴
- 如果当前记录是富文本，可以按 `Ctrl + Shift + V` 以纯文本方式粘贴
- 用 `Ctrl + P` 固定常用内容，比如常用回复、邮箱地址或命令
- 用 `Delete` 删除当前记录
- 不想继续记录时，可以在托盘里暂停；需要时再恢复

### 常见用法

- 快速回复聊天消息、邮件和工单
- 在不同应用之间重复粘贴固定文本
- 暂存截图、复制的文件和格式化内容
- 通过设置页调整快捷键、历史条数和存储位置

### 默认操作

- 打开面板：`Alt + Space`
- 选中记录后回车：粘贴当前记录
- 纯文本粘贴：`Ctrl + Shift + V`
- 固定/取消固定：`Ctrl + P`
- 删除记录：`Delete`

### 运行发布版

如果你下载的是发布包，直接运行 `CipherClip.exe` 即可。

- 首次启动时，默认会在 `CipherClip.exe` 同级的 `data` 目录保存数据

## 源码与开发

### 项目结构

- `backend/`: Python 3.12, `pywebview`, `pystray`
- `frontend/`: React, Vite, TypeScript
- `scripts/`: 构建脚本

### 首次安装

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt

Set-Location .\frontend
npm install
Set-Location ..
```

### 本地开发

先启动前端开发服务器：

```powershell
Set-Location .\frontend
npm run dev
```

再在仓库根目录启动桌面端：

```powershell
$env:CLIPBOARD_DEV="1"
.\.venv\Scripts\python backend\main.py
```

### 静态运行

```powershell
Set-Location .\frontend
npm run build
Set-Location ..

$env:CLIPBOARD_DEV="0"
.\.venv\Scripts\python backend\main.py
```

### 测试

```powershell
Set-Location .\frontend
npm run test:run
npm run build
npm run lint
Set-Location ..

.\.venv\Scripts\python -m pytest backend/tests -q
```

### 打包发布

```powershell
.\scripts\build-release.ps1
```

输出目录：

- `dist\CipherClip`
