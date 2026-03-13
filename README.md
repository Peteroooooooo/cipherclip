[English](README.en.md)

# CipherClip

一个 Windows 剪贴板历史工具，基于 Python、pywebview、pystray、React 和 Vite 构建。

## 功能与使用

### 功能

- 记录文本、富文本、图片和文件复制历史
- 支持固定常用内容，避免被新记录顶掉
- 支持托盘常驻、暂停记录、清空历史
- 支持自定义快捷键、历史上限和存储位置
- 支持开机启动

### 默认操作

- 打开面板：`Alt + Space`
- 选中记录后回车：执行主操作
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
