# CipherClip

Windows-only clipboard history desktop app built with Python, pywebview, pystray, React, and Vite.

## Stack

- `backend/`: Python 3.12 + `pywebview` + `pystray`
- `frontend/`: React + Vite + TypeScript

## What is included

- quick panel shell
- settings shell
- tray menu
- real clipboard capture controls for text, rich text, images, and files
- history retention and clear-all behavior
- Python/JS bridge
- frontend and backend tests

## First-time setup

### Python

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

### Frontend

```powershell
cd frontend
npm install
```

## Default run

If `frontend/dist/index.html` already exists, the desktop shell now loads the built frontend by default:

```powershell
# from the repository root
.\.venv\Scripts\python backend\main.py
```

## Development mode

Start the Vite dev server in one terminal:

```powershell
Set-Location .\frontend
npm run dev
```

Start the desktop shell in another terminal:

```powershell
# from the repository root
$env:CLIPBOARD_DEV="1"
.\.venv\Scripts\python backend\main.py
```

The desktop shell will load `http://127.0.0.1:5173`.

If you also want pywebview debug tools:

```powershell
# from the repository root
$env:CLIPBOARD_DEV="1"
$env:CLIPBOARD_DEBUG="1"
.\.venv\Scripts\python backend\main.py
```

## Static mode

Build the frontend first:

```powershell
Set-Location .\frontend
npm run build
```

Then start the desktop shell with dev mode disabled:

```powershell
# from the repository root
$env:CLIPBOARD_DEV="0"
.\.venv\Scripts\python backend\main.py
```

The desktop shell will load `frontend/dist/index.html`.

## Verification

```powershell
cd frontend
npm run test:run
npm run build
```

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
```

## Release build

Build a Windows distributable with PyInstaller:

```powershell
.\scripts\build-release.ps1
```

Output will be created under `dist\CipherClip`.

The packaged app:

- loads `frontend/dist` as bundled static assets
- stores default user data under `%LOCALAPPDATA%\CipherClip\data`
- supports launch-on-startup registration through the Windows `Run` key
- starts hidden when launched from the startup entry
