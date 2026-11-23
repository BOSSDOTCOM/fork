# SPDX-License-Identifier: GPL-3.0-or-later
# The kernel's pool usage by tag, read-only, without admin rights or extra tools (owner, 2026-11-22): the data
# poolmon shows, from NtQuerySystemInformation(SystemPoolTagInformation = 22). On 2026-11-22 the paged pool had
# reached 10.4 GB, 4.1 GB of it under the tag Toke (about 2.0 million token objects), after 15 days without a
# real restart. tools/jobs/sweep.sh logs the Toke line every run.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/jobs/pool_tags.ps1 [-Top 15]   the largest paged tags
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/jobs/pool_tags.ps1 -Tag Toke     one line: TAG MB LIVE
#
# LIVE is allocations minus frees (the objects alive now). The x64 SYSTEM_POOLTAG record is 40 bytes: Tag[4],
# PagedAllocs, PagedFrees, padding, PagedUsed (8 bytes), NonPagedAllocs, NonPagedFrees, NonPagedUsed (8 bytes);
# the array starts at offset 8, after the ULONG count.
param([int]$Top = 15, [string]$Tag = '')
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ForkPoolTags {
    [DllImport("ntdll.dll")]
    public static extern int NtQuerySystemInformation(int cls, IntPtr buf, int len, out int ret);
}
'@
$len = 1MB
while ($true) {
    $buf = [Runtime.InteropServices.Marshal]::AllocHGlobal($len)
    $ret = 0
    $st = [ForkPoolTags]::NtQuerySystemInformation(22, $buf, $len, [ref]$ret)
    if ($st -eq [int]0xC0000004) {   # STATUS_INFO_LENGTH_MISMATCH: grow and retry
        [Runtime.InteropServices.Marshal]::FreeHGlobal($buf)
        $len = [Math]::Max($ret, $len * 2)
        continue
    }
    break
}
if ($st -ne 0) { "NtQuerySystemInformation failed: 0x{0:X8}" -f $st; exit 1 }
$m = [Runtime.InteropServices.Marshal]
$count = $m::ReadInt32($buf, 0)
$rows = for ($i = 0; $i -lt $count; $i++) {
    $o = 8 + 40 * $i
    [pscustomobject]@{
        Tag        = -join (0..3 | ForEach-Object { [char]$m::ReadByte($buf, $o + $_) })
        PagedMB    = [Math]::Round($m::ReadInt64($buf, $o + 16) / 1MB, 1)
        PagedLive  = $m::ReadInt32($buf, $o + 4) - $m::ReadInt32($buf, $o + 8)
        NonPagedMB = [Math]::Round($m::ReadInt64($buf, $o + 32) / 1MB, 1)
    }
}
$m::FreeHGlobal($buf)
if ($Tag) {
    $r = $rows | Where-Object { $_.Tag -eq $Tag } | Select-Object -First 1
    if ($r) { "{0} {1} {2}" -f $r.Tag, $r.PagedMB, $r.PagedLive } else { "$Tag 0 0" }
    exit 0
}
"{0} tags; paged total {1:N0} MB" -f $count, (($rows | Measure-Object PagedMB -Sum).Sum)
$rows | Sort-Object PagedMB -Descending | Select-Object -First $Top | Format-Table -AutoSize | Out-String
