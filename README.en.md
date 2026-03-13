[中文](README.md)

# CipherClip

A Windows clipboard history tool built with Python, pywebview, pystray, React, and Vite.

## Features and Usage

### Features

- Capture text, rich text, images, and copied files
- Pin important items so they stay in history
- Run from the tray, pause capture, and clear history
- Customize shortcuts, history limits, and storage path
- Support launch on startup

### Default actions

- Open panel: `Alt + Space`
- Primary action on selected item: `Enter`
- Paste as plain text: `Ctrl + Shift + V`
- Pin or unpin: `Ctrl + P`
- Delete item: `Delete`

### Run the packaged app

If you are using a release build, launch `CipherClip.exe`.

- On first launch, data is stored in the `data` folder beside `CipherClip.exe` by default

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

- `dist\CipherClip`
