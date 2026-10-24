# Puts the winget-installed toolchain on PATH and names the compilers the
# CMake presets use. Dot-source it: . scripts\env.ps1
$pk = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
function Find-Dir($pattern) {
  $d = Get-ChildItem -Path $pk -Directory -Filter $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $d) { throw "toolchain package not found: $pattern (see docs/DESIGN.md section 2)" }
  $d.FullName
}
$llvm = Get-ChildItem (Find-Dir 'MartinStorsjo.LLVM-MinGW.UCRT*') -Directory -Filter 'llvm-mingw-*' | Select-Object -First 1
$cmake = Get-ChildItem (Find-Dir 'Kitware.CMake*') -Directory -Filter 'cmake-*' | Select-Object -First 1
$ninja = Find-Dir 'Ninja-build.Ninja*'
$gcc = Join-Path (Find-Dir 'BrechtSanders.WinLibs.POSIX.UCRT*') 'mingw64\bin'

$env:FORK_CLANG_CXX = (Join-Path $llvm.FullName 'bin\clang++.exe') -replace '\\', '/'
$env:FORK_GCC_CXX = (Join-Path $gcc 'g++.exe') -replace '\\', '/'
# llvm-mingw first: sanitizer and libc++ DLLs for clang debug builds live there.
# GCC is always used through its absolute path, so its bin dir goes last.
$env:PATH = "$(Join-Path $llvm.FullName 'bin');$(Join-Path $cmake.FullName 'bin');$ninja;$env:PATH;$gcc"
