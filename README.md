[English](README.en.md)

# CipherClip

一个 Windows 剪贴板历史工具，基于 Python、pywebview、pystray、React 和 Vite 构建。

**[在线体验 Demo](https://peteroooooooo.github.io/cipherclip/)** · **[下载最新版](https://github.com/Peteroooooooo/cipherclip/releases/latest)**

<p align="center"><img src="assets/demo-panel.png" alt="CipherClip 面板：标题栏的玻璃胶囊、固定与最近的剪贴板记录，悬停的那一行右侧是操作胶囊" width="400"></p>

在线 Demo 就是真实的面板界面，只是用示例数据代替了你的剪贴板：可以切换筛选、搜索、固定、删除，体验悬停效果和设置页。真正读写剪贴板、粘贴回原窗口需要下载 Windows 版。

## 新版本亮点

- **液态玻璃界面（1.1）**：面板是一块磨砂玻璃，背后是实时模糊的桌面；标题栏和每行的操作按钮是带折射边缘的玻璃胶囊，按钮之间有一颗液态玻璃小透镜跟着鼠标滑动。
- **磁吸胶囊（1.2）**：鼠标悬停时胶囊弹性放大、带回弹地跟着鼠标微移，鼠标下方出现镜面高光，旁边的胶囊会让位；按下时会压扁一下。
- **来源应用图标（1.1）**：每条记录显示复制它的那个应用的图标。
- **自动去重（1.2）**：同一段文字再次复制，不会新增记录，而是把原来那条移到最前面。浏览器每次复制套的格式不同，纯文本和带格式的版本也算同一条。
- **更省资源（1.1）**：面板隐藏在托盘时几乎不占 CPU，第一次呼出也不再卡顿。

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

如果你下载的是发布包，解压后把 `CipherClip.exe` 放进一个固定的文件夹（比如 `D:\Apps\CipherClip\`），直接运行即可。

- 剪贴板历史、图片和设置保存在 `CipherClip.exe` 同级的 `data` 目录；搬家时连同 `data` 一起移动，换新版本时只替换 exe
- WebView2 的浏览器缓存在 `%LOCALAPPDATA%\CipherClip\WebView2`，删掉不会丢历史，下次启动会重新生成
- 需要系统自带的 Microsoft Edge WebView2 Runtime（Windows 11 已内置）
- 同一时间只运行一个 CipherClip：再次打开只会唤出已运行的那一个
- 打包脚本会重新生成发布产物，但不会主动删除这个 `data` 目录

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

- `dist\CipherClip.exe`

实时毛玻璃（live glass）需要的原生组件由 `scripts\build-native.ps1` 编译，需要 Visual Studio Build Tools（C++ 工作负载）和 Windows SDK；没有它们时打包仍会成功，只是发布版改用截图式玻璃。

### 在线 Demo

前端在普通浏览器里运行时会使用示例数据（`frontend/src/app/pywebview.ts`）。每次 `frontend/` 的改动推送到 `main`，`.github/workflows/demo.yml` 会重新打包并发布到 GitHub Pages。本地预览：在 `frontend` 目录下运行 `npm run build`，再运行 `npm run preview`。
