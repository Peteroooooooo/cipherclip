[中文](README.md)

# CipherClip

A Windows clipboard history tool built with Python, pywebview, pystray, React, and Vite.

## Features and Usage

### Quick start

- Leave your cursor in a chat box, input field, or editor, then press `Alt + Space`
- Pick a history item with the keyboard or mouse, then press `Enter` to paste it back into the original target
- For rich text entries, use `Ctrl + Shift + V` to paste as plain text
- Use `Ctrl + P` to pin frequently reused content such as replies, email addresses, or commands
- Use `Delete` to remove the current item
- Pause capture from the tray whenever you do not want new clipboard activity recorded

### Common use cases

- Reuse replies in chats, email, and support tools
- Keep important snippets pinned across apps
- Store screenshots, copied files, and formatted content in one place
- Adjust shortcuts, history limits, and storage path from Settings

### Default actions

- Open panel: `Alt + Space`
- Paste selected item: `Enter`
- Paste as plain text: `Ctrl + Shift + V`
- Pin or unpin: `Ctrl + P`
- Delete item: `Delete`

### Run the packaged app

If you are using a release build, unzip it, put `CipherClip.exe` in a permanent folder (for example `D:\Apps\CipherClip\`) and launch it.

- Clipboard history, images and settings live in the `data` folder beside `CipherClip.exe`; move the two together, and to upgrade replace only the exe
- WebView2's browser cache lives in `%LOCALAPPDATA%\CipherClip\WebView2`; deleting it loses no history, it is rebuilt on the next launch
- Requires the Microsoft Edge WebView2 Runtime (built into Windows 11)
- Only one CipherClip runs at a time: launching it again just brings up the running one
- The release build script rebuilds the release artifact, but it does not proactively delete this `data` folder

## Source and Development

### Project layout

- `backend/`: Python 3.12, `pywebview`, `pystray`
- `frontend/`: React, Vite, TypeScript
- `scripts/`: build scripts

### First-time setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt

Set-Location .\frontend
npm install
Set-Location ..
```

### Local development

Start the frontend dev server:

```powershell
Set-Location .\frontend
npm run dev
```

Then start the desktop app from the repository root:

```powershell
$env:CLIPBOARD_DEV="1"
.\.venv\Scripts\python backend\main.py
```

### Static mode

```powershell
Set-Location .\frontend
npm run build
Set-Location ..

$env:CLIPBOARD_DEV="0"
.\.venv\Scripts\python backend\main.py
```

### Verification

```powershell
Set-Location .\frontend
npm run test:run
npm run build
npm run lint
Set-Location ..

.\.venv\Scripts\python -m pytest backend/tests -q
```

### Release build

```powershell
.\scripts\build-release.ps1
```

Output:

- `dist\CipherClip.exe`

The native part of the live glass is compiled by `scripts\build-native.ps1`, which needs Visual Studio Build Tools (C++ workload) and the Windows SDK; without them the build still succeeds and the release uses snapshot glass instead.
