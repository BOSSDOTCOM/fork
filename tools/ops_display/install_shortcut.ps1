# SPDX-License-Identifier: GPL-3.0-or-later
# Creates the desktop shortcut "Fork Operations Display": it starts the display's local server without a
# console window and opens the page. The display only reads; closing its page leaves the server running
# (it uses under 1% of one core); end it from Task Manager (pythonw.exe ... serve.py) or log off.
#   powershell -ExecutionPolicy Bypass -File tools\ops_display\install_shortcut.ps1
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repo '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $python)) { throw "pythonw.exe not found in the repository's .venv ($python)" }
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Fork Operations Display.lnk'))
$link.TargetPath = $python
$link.Arguments = '-I -B "' + (Join-Path $PSScriptRoot 'serve.py') + '" --open'
$link.WorkingDirectory = $PSScriptRoot
$link.Description = 'Fork Operations Display (display only)'
$link.Save()
Write-Output "Shortcut created on the desktop: Fork Operations Display"
