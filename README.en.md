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

If you are using a release build, launch `CipherClip.exe`.

- On first launch, data is stored in the `data` folder beside `CipherClip.exe` by default
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
