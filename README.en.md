[中文](README.md)

# CipherClip

A clipboard history tool for Windows, with a liquid glass interface.

**[Live demo](https://peteroooooooo.github.io/cipherclip/)** · **[Download](https://github.com/Peteroooooooo/cipherclip/releases/latest)**

<p align="center"><img src="assets/demo-panel.png" alt="The CipherClip panel" width="400"></p>

## Usage

1. Download `CipherClip.zip`, put `CipherClip.exe` in a permanent folder and run it.
2. Press `Alt + Space` to open the panel, pick a clip and press `Enter` to paste it where you were typing.

| Shortcut | Action |
|---|---|
| `Alt + Space` | Open the panel |
| `Enter` | Paste |
| `Ctrl + Shift + V` | Paste as plain text |
| `Ctrl + P` | Pin / unpin |
| `Delete` | Delete |

History is kept in the `data` folder next to the exe; to upgrade, replace only the exe. Needs the WebView2 Runtime (built into Windows 11).

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
cd frontend; npm install; npm run build; cd ..
.\.venv\Scripts\python backend\main.py
```

Release build: `.\scripts\build-release.ps1`, output `dist\CipherClip.exe`.
