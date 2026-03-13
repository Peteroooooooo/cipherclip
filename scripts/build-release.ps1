Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found at $python"
}

Write-Host "Building frontend..."
Push-Location (Join-Path $projectRoot "frontend")
try {
    npm run build
}
finally {
    Pop-Location
}

Write-Host "Installing build dependencies..."
& $python -m pip install -r (Join-Path $projectRoot "backend\requirements.txt") -r (Join-Path $projectRoot "backend\requirements-build.txt")

Write-Host "Packaging CipherClip..."
& $python -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "CipherClip.spec")

Write-Host "Build complete. Output: $(Join-Path $projectRoot 'dist\CipherClip')"
