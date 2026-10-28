# SPDX-License-Identifier: GPL-3.0-or-later
# Configure, build and test presets; prints a summary table.
#   scripts\build.ps1                     all presets, then PGO for both compilers
#   scripts\build.ps1 clang-debug gcc-v3  chosen presets (clang-pgo / gcc-pgo run PGO)
#   $env:FORK_SLOW = '1' adds the slow-labelled tests (full-depth perft in debug builds)
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
. (Join-Path $PSScriptRoot 'env.ps1')

$all = 'clang-debug', 'clang-release', 'clang-v3', 'clang-avx512', 'clang-nopext',
       'gcc-debug', 'gcc-release', 'gcc-v3', 'gcc-avx512', 'gcc-nopext', 'clang-pgo', 'gcc-pgo'
$presets = if ($args.Count) { $args } else { $all }
$ctestArgs = @('--output-on-failure')
if ($env:FORK_SLOW -ne '1') { $ctestArgs += '-LE', 'slow' }

$results = foreach ($p in $presets) {
  Write-Host "=== $p"
  $ok = $true
  if ($p -in 'clang-pgo', 'gcc-pgo') {
    $cxx, $id = if ($p -eq 'gcc-pgo') { $env:FORK_GCC_CXX, 'GNU' } else { $env:FORK_CLANG_CXX, 'Clang' }
    cmake "-DSOURCE_DIR=$($root -replace '\\','/')" "-DCXX=$cxx" "-DCOMPILER_ID=$id" -P cmake/pgo.cmake
    $ok = $LASTEXITCODE -eq 0
  } else {
    cmake --preset $p | Out-Null
    if ($LASTEXITCODE -eq 0) { cmake --build "build/$p" }
    if ($LASTEXITCODE -eq 0) { ctest --test-dir "build/$p" @ctestArgs }
    $ok = $LASTEXITCODE -eq 0
  }
  [pscustomobject]@{ Preset = $p; Result = if ($ok) { 'PASS' } else { 'FAIL' } }
}
$results | Format-Table -AutoSize
if ($results.Result -contains 'FAIL') { exit 1 }
