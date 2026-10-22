# Builds backend/native into backend/native/bin: cipherclip_backdrop.dll (live glass) and
# cipherclip_capture.exe (the screen capture helper it starts).
# Needs Visual Studio Build Tools (C++ workload) and the Windows 10/11 SDK.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$nativeDir = Join-Path $root 'backend\native'
$outDir = Join-Path $nativeDir 'bin'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'vswhere.exe not found; install Visual Studio Build Tools.' }
$vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) { throw 'MSVC x64 tools not found.' }
$vcvars = Join-Path $vsPath 'VC\Auxiliary\Build\vcvars64.bat'

$objDir = Join-Path $outDir 'obj'
New-Item -ItemType Directory -Force -Path $objDir | Out-Null
$dll = Join-Path $outDir 'cipherclip_backdrop.dll'
$exe = Join-Path $outDir 'cipherclip_capture.exe'
$common = "/nologo /std:c++17 /EHsc /O2 /MT /W3 /I`"$nativeDir`" /Fo`"$objDir\\`""

# vcvars64 only works inside cmd, so the compile runs through a small generated batch file.
$batch = Join-Path $objDir 'build.cmd'
@(
  '@echo off'
  "call `"$vcvars`" >nul || exit /b 1"
  "cl $common /LD `"$nativeDir\live_backdrop.cpp`" /link /OUT:`"$dll`" /IMPLIB:`"$objDir\cipherclip_backdrop.lib`" windowsapp.lib dwmapi.lib CoreMessaging.lib d3d11.lib d2d1.lib dxguid.lib user32.lib || exit /b 1"
  "cl $common `"$nativeDir\capture_helper.cpp`" /link /OUT:`"$exe`" /SUBSYSTEM:WINDOWS Magnification.lib user32.lib || exit /b 1"
) | Set-Content -LiteralPath $batch -Encoding ascii

& cmd.exe /d /c $batch
if ($LASTEXITCODE -ne 0) { throw "native build failed ($LASTEXITCODE)" }
Write-Output "built $dll"
Write-Output "built $exe"
