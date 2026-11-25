# SPDX-License-Identifier: GPL-3.0-or-later
# Each WSL distro's virtual disk file and its size on C: (owner, 2026-11-24: the sweep tracks C: and the Ubuntu vhdx
# size). Read-only. The distros come from the registry (HKCU ...\Lxss: DistributionName, BasePath), so no path is
# written here. One line, e.g. "Ubuntu 143.12 GB, Ubuntu-22.04 23.74 GB"; a distro whose ext4.vhdx is missing shows "?".
$items = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue |
    ForEach-Object { Get-ItemProperty $_.PSPath } | Where-Object { $_.DistributionName -and $_.BasePath }
$parts = foreach ($d in $items | Sort-Object DistributionName) {
    $base = $d.BasePath -replace '^\\\\\?\\', ''
    $f = Join-Path $base 'ext4.vhdx'
    if (Test-Path -LiteralPath $f) { '{0} {1:N2} GB' -f $d.DistributionName, ((Get-Item -LiteralPath $f).Length / 1e9) }
    else { '{0} ?' -f $d.DistributionName }
}
if ($parts) { $parts -join ', ' } else { 'no WSL distros found' }
