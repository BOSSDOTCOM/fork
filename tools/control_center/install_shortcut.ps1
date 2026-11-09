# SPDX-License-Identifier: GPL-3.0-or-later
# Puts a "Fork Control Center" shortcut on the desktop. It runs app.py from this folder with the
# repository's Python (windowless pythonw.exe, isolated mode).
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\control_center\install_shortcut.ps1 [-Python PATH]
param([string]$Python = (Join-Path $HOME 'fork\.venv\Scripts\pythonw.exe'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Python)) { throw "no Python at $Python (give -Python PATH to a pythonw.exe with tkinter)" }
$app = Join-Path $PSScriptRoot 'app.py'
$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop 'Fork Control Center.lnk'
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($link)
$s.TargetPath = $Python
$s.Arguments = "-I `"$app`""
$s.WorkingDirectory = $PSScriptRoot
$s.Description = 'Fork Control Center: data generation, jobs, testing, training, networks, data, machine, roadmap'
$s.Save()
"shortcut: $link -> $Python -I $app"
