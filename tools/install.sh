#!/usr/bin/env bash
# Fork testing-tool installer for WSL2 Ubuntu.
#
# STATUS: first real run 2026-10-23 on Ubuntu 26.04 (WSL2): all steps PASS or SKIP
# (6-piece Syzygy declined, hotspot skipped).
#
# What it does (each step is skipped if already done, then re-verified):
#   1. apt build deps + profilers (needs sudo: you will be asked for your password once)
#   2. fastchess      built from the pinned tag in tools/versions.lock
#   3. cutechess-cli  built from the pinned tag (needs Qt >= 6.8); falls back to the
#                     pinned AppImage if the distro Qt is too old (see CUTECHESS_MODE)
#   4. Ordo           built from the pinned tag
#   5. Syzygy 3-4-5   290 files (~0.98 GB) from tablebase.lichess.ovh, every file sha256-checked
#   6. Syzygy 6-piece OPTIONAL, interactive y/N only (WDL 72.8 GB, DTZ 87.4 GB); skipped when
#                     stdin is not a terminal
#   7. perf, valgrind (apt), optional hotspot AppImage (FORK_TOOLS_HOTSPOT=1)
#   Then smoke tests and a PASS/FAIL/SKIP table. Exit code is 1 if anything failed.
#
# Environment variables:
#   FORK_TOOLS_PREFIX   install prefix (default: ~/fork-tools)
#   CUTECHESS_MODE      auto (default) | source | appimage
#   FORK_TOOLS_HOTSPOT  1 to also fetch the hotspot perf GUI AppImage (default 0)
#   JOBS                parallel build jobs (default: nproc)
#
# Usage:  bash tools/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${SCRIPT_DIR}/versions.lock"
PREFIX="${FORK_TOOLS_PREFIX:-$HOME/fork-tools}"
BIN="${PREFIX}/bin"
SRC="${PREFIX}/src"
STAMPS="${PREFIX}/.stamps"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 2)}"
CUTECHESS_MODE="${CUTECHESS_MODE:-auto}"
FORK_TOOLS_HOTSPOT="${FORK_TOOLS_HOTSPOT:-0}"

declare -A RESULT=()
declare -A NOTE=()
ORDER=()

log()  { printf '\033[1;34m[fork-tools]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[fork-tools] WARNING:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[fork-tools] ERROR:\033[0m %s\n' "$*" >&2; }

# ---------------------------------------------------------------- lock file
[[ -f "$LOCK" ]] || { err "missing $LOCK"; exit 1; }

# lock_get NAME FIELD   (FIELD: 2=version 3=url 4=hash)
lock_get() {
  local v
  v="$(awk -v n="$1" -v f="$2" '!/^#/ && NF>=4 && $1==n {print $f; exit}' "$LOCK")"
  [[ -n "$v" ]] || { err "versions.lock has no entry '$1'"; return 1; }
  printf '%s\n' "$v"
}
# strip "sha256:" / "commit:" prefix
lock_hash() { local h; h="$(lock_get "$1" 4)" || return 1; printf '%s\n' "${h#*:}"; }

# ---------------------------------------------------------------- step runner
# run_step NAME FUNCTION: runs FUNCTION in a subshell with errexit on, records the outcome.
# A function may 'return 2' (via skip) to mark the step SKIP.
run_step() {
  local name="$1" fn="$2" rc
  ORDER+=("$name")
  log "=== ${name} ==="
  set +e
  ( set -euo pipefail; "$fn" )
  rc=$?
  set -e
  case "$rc" in
    0) RESULT[$name]=PASS ;;
    2) RESULT[$name]=SKIP ;;
    *) RESULT[$name]=FAIL; err "step '${name}' failed (exit ${rc}); continuing with the next step" ;;
  esac
  [[ -f "${STAMPS}/${name}.note" ]] && NOTE[$name]="$(cat "${STAMPS}/${name}.note")"
  return 0
}
note() { printf '%s' "$*" > "${STAMPS}/${CURRENT_STEP}.note"; }
skip() { note "$*"; log "skip: $*"; exit 2; }

# ---------------------------------------------------------------- helpers
# fetch URL OUT SHA256   download (resumable) and verify; keeps an already-verified file
fetch() {
  local url="$1" out="$2" sha="$3"
  if [[ -f "$out" ]] && echo "${sha}  ${out}" | sha256sum -c --status -; then
    return 0
  fi
  curl -fL --retry 5 --retry-delay 5 -C - -o "${out}.part" "$url"
  echo "${sha}  ${out}.part" | sha256sum -c --status - || { err "sha256 mismatch for $url"; rm -f "${out}.part"; return 1; }
  mv "${out}.part" "$out"
}

# git_checkout REPO_URL DIR TAG EXPECTED_COMMIT
git_checkout() {
  local url="$1" dir="$2" tag="$3" want="$4" got
  if [[ ! -d "$dir/.git" ]]; then
    git clone --quiet "$url" "$dir"
  fi
  git -C "$dir" fetch --quiet --tags origin
  git -C "$dir" -c advice.detachedHead=false checkout --quiet "refs/tags/${tag}"
  got="$(git -C "$dir" rev-parse 'HEAD^{commit}')"
  if [[ "$got" != "$want" ]]; then
    err "tag ${tag} of ${url} resolves to ${got}, versions.lock expects ${want}. Upstream re-tagged? Refusing to build."
    return 1
  fi
}

stamp_ok()  { [[ -f "${STAMPS}/$1" && "$(cat "${STAMPS}/$1")" == "$2" ]]; }
stamp_set() { printf '%s' "$2" > "${STAMPS}/$1"; }

version_ge() { [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]; }

# ================================================================= steps
step_apt() {
  CURRENT_STEP=apt-deps
  local pkgs=(build-essential git cmake pkg-config curl ca-certificates coreutils
              qt6-base-dev qt6-base-dev-tools qt6-svg-dev qt6-5compat-dev
              valgrind linux-tools-common linux-tools-generic)
  local missing=() p
  for p in "${pkgs[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
  done
  if ((${#missing[@]} == 0)); then
    note "all ${#pkgs[@]} packages already installed"
    return 0
  fi
  log "Missing apt packages: ${missing[*]}"
  local SUDO=""
  if [[ $EUID -ne 0 ]]; then
    SUDO=sudo
    log "sudo will now ask for YOUR Linux (WSL) password to install packages."
  fi
  $SUDO apt-get update
  $SUDO apt-get install -y "${missing[@]}"
  note "installed: ${missing[*]}"
}

step_fastchess() {
  CURRENT_STEP=fastchess
  local tag commit url dir
  tag="$(lock_get fastchess 2)"; url="$(lock_get fastchess 3)"; commit="$(lock_hash fastchess)"
  dir="${SRC}/fastchess"
  if stamp_ok fastchess "$commit" && [[ -x "${BIN}/fastchess" ]]; then
    note "already built ${tag}"
  else
    git_checkout "$url" "$dir" "$tag" "$commit"
    make -C "$dir" clean >/dev/null 2>&1 || true
    make -C "$dir" -j"$JOBS"
    install -m 0755 "${dir}/fastchess" "${BIN}/fastchess"
    stamp_set fastchess "$commit"
    note "built ${tag}"
  fi
  # smoke test
  "${BIN}/fastchess" -version
}

cutechess_from_source() {
  local tag="$1" url="$2" commit="$3" dir="${SRC}/cutechess"
  git_checkout "$url" "$dir" "$tag" "$commit"
  rm -rf "${dir}/build"
  cmake -S "$dir" -B "${dir}/build" -DCMAKE_BUILD_TYPE=Release -DWITH_TESTS=OFF
  cmake --build "${dir}/build" --target cli -j"$JOBS"
  install -m 0755 "${dir}/build/cutechess-cli" "${BIN}/cutechess-cli"
}

cutechess_from_appimage() {
  local url sha opt img cli
  url="$(lock_get cutechess-appimage 3)"; sha="$(lock_hash cutechess-appimage)"
  opt="${PREFIX}/opt/cutechess-appimage"; img="${PREFIX}/downloads/Cute_Chess.AppImage"
  fetch "$url" "$img" "$sha"
  chmod +x "$img"
  rm -rf "$opt"; mkdir -p "$opt"
  # --appimage-extract needs no FUSE (WSL often lacks it)
  ( cd "$opt" && "$img" --appimage-extract >/dev/null )
  # UNVERIFIED that the AppImage ships cutechess-cli; look for it.
  cli="$(find "${opt}/squashfs-root" -type f -name 'cutechess-cli' -perm -u+x | head -n1 || true)"
  if [[ -z "$cli" ]]; then
    err "the cutechess AppImage does not contain cutechess-cli. Install Qt >= 6.8 (newer Ubuntu) and rerun with CUTECHESS_MODE=source."
    return 1
  fi
  cat > "${BIN}/cutechess-cli" <<EOF
#!/usr/bin/env bash
export LD_LIBRARY_PATH="${opt}/squashfs-root/usr/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export QT_QPA_PLATFORM=offscreen
exec "${cli}" "\$@"
EOF
  chmod 0755 "${BIN}/cutechess-cli"
}

step_cutechess() {
  CURRENT_STEP=cutechess-cli
  local tag url commit qtver="" mode="$CUTECHESS_MODE"
  tag="$(lock_get cutechess 2)"; url="$(lock_get cutechess 3)"; commit="$(lock_hash cutechess)"
  if stamp_ok cutechess "${commit}" && [[ -x "${BIN}/cutechess-cli" ]]; then
    note "already installed ${tag}"
  else
    qtver="$(pkg-config --modversion Qt6Core 2>/dev/null || true)"
    if [[ "$mode" == auto ]]; then
      if [[ -n "$qtver" ]] && version_ge "$qtver" 6.8; then mode=source; else mode=appimage; fi
    fi
    log "Qt6Core from pkg-config: '${qtver:-none}'; cutechess mode: ${mode} (README requires Qt >= 6.8)"
    case "$mode" in
      source)   cutechess_from_source "$tag" "$url" "$commit"; note "built ${tag} from source (Qt ${qtver})" ;;
      appimage) cutechess_from_appimage; note "${tag} via AppImage (distro Qt '${qtver:-none}' < 6.8)" ;;
      *) err "CUTECHESS_MODE must be auto, source or appimage"; return 1 ;;
    esac
    stamp_set cutechess "$commit"
  fi
  "${BIN}/cutechess-cli" -version
}

step_ordo() {
  CURRENT_STEP=ordo
  local tag url commit dir out
  tag="$(lock_get ordo 2)"; url="$(lock_get ordo 3)"; commit="$(lock_hash ordo)"
  dir="${SRC}/Ordo"
  if stamp_ok ordo "$commit" && [[ -x "${BIN}/ordo" ]]; then
    note "already built ${tag}"
  else
    git_checkout "$url" "$dir" "$tag" "$commit"
    make -C "$dir" clean >/dev/null 2>&1 || true
    # Ordo's last release is from 2016. If a modern GCC rejects it (e.g. -fno-common default
    # since GCC 10), retry with -fcommon. Its own 'make install' writes to /usr/local, so copy instead.
    if ! make -C "$dir" ordo; then
      warn "Ordo build failed with default flags; retrying with -fcommon"
      make -C "$dir" clean >/dev/null 2>&1 || true
      make -C "$dir" ordo CFLAGS="-DNDEBUG -DMY_SEMAPHORES -flto -I myopt -I sysport -fcommon"
    fi
    install -m 0755 "${dir}/ordo" "${BIN}/ordo"
    stamp_set ordo "$commit"
    note "built ${tag}"
  fi
  out="$("${BIN}/ordo" -h 2>&1 || true)"
  printf '%s\n' "$out" | head -n 5
  printf '%s' "$out" | grep -qi 'ordo'
}

# syzygy_list MIN MAX  -> lines "sha256  name" for tables with MIN..MAX pieces
syzygy_list() {
  awk -v lo="$1" -v hi="$2" 'NF==2 {
      n=$2; sub(/^\*/, "", n); b=n; sub(/\..*$/, "", b); gsub(/[^KQRBNP]/, "", b);
      if (length(b) >= lo && length(b) <= hi) print $1 "  " n }' "${PREFIX}/syzygy/sha256"
}

syzygy_sha_list() {
  local url sha
  url="$(lock_get syzygy-sha256-list 3)"; sha="$(lock_hash syzygy-sha256-list)"
  mkdir -p "${PREFIX}/syzygy"
  fetch "$url" "${PREFIX}/syzygy/sha256" "$sha"
}

# syzygy_get DESTDIR LISTFILE WDL_URL DTZ_URL   (download missing, then verify all)
syzygy_get() {
  local dest="$1" list="$2" wurl="$3" zurl="$4" name base
  mkdir -p "$dest"
  while read -r _ name; do
    [[ -f "${dest}/${name}" ]] && continue
    case "$name" in
      *.rtbw) base="$wurl" ;;
      *.rtbz) base="$zurl" ;;
      *) continue ;;
    esac
    log "downloading ${name}"
    curl -fL --retry 5 --retry-delay 5 -C - -o "${dest}/${name}.part" "${base}${name}"
    mv "${dest}/${name}.part" "${dest}/${name}"
  done < "$list"
  log "verifying sha256 of $(wc -l < "$list") files in ${dest}"
  ( cd "$dest" && sha256sum -c --quiet "$list" )
}

count_tb() { find "$1" -maxdepth 1 -type f -name "*.$2" | wc -l; }

step_syzygy345() {
  CURRENT_STEP=syzygy-3-4-5
  local dest="${PREFIX}/syzygy/3-4-5" list w z
  syzygy_sha_list
  list="${PREFIX}/syzygy/3-4-5.sha256"
  syzygy_list 3 5 > "$list"
  [[ "$(wc -l < "$list")" -eq 290 ]] || { err "expected 290 entries for 3-5 pieces in checksum list"; return 1; }
  syzygy_get "$dest" "$list" "$(lock_get syzygy-345-wdl 3)" "$(lock_get syzygy-345-dtz 3)"
  w="$(count_tb "$dest" rtbw)"; z="$(count_tb "$dest" rtbz)"
  log "3-4-5: ${w} .rtbw, ${z} .rtbz (expected 145 + 145)"
  note "${w} rtbw + ${z} rtbz, sha256 OK"
  [[ "$w" -eq 145 && "$z" -eq 145 ]]
}

step_syzygy6() {
  CURRENT_STEP=syzygy-6
  local dest="${PREFIX}/syzygy/6" list ans want_wdl=0 want_dtz=0 avail_gb need_gb=0 w z
  if [[ ! -t 0 ]]; then
    skip "non-interactive shell; 6-piece download needs an interactive y/N"
  fi
  echo
  echo "Optional 6-piece Syzygy (365 tables) from tablebase.lichess.ovh:"
  echo "   WDL only : 365 .rtbw files,  72.8 GB (67.8 GiB)  - enough for search and for fastchess/cutechess -tb adjudication"
  echo "   + DTZ    : 365 .rtbz files,  87.4 GB (81.4 GiB)  - root move choice only; full set 160.2 GB (149.2 GiB)"
  read -r -p "Download 6-piece WDL tables (72.8 GB)? [y/N] " ans || ans=""
  [[ "$ans" =~ ^[Yy]$ ]] && want_wdl=1
  if ((want_wdl)); then
    read -r -p "Also download 6-piece DTZ tables (another 87.4 GB)? [y/N] " ans || ans=""
    [[ "$ans" =~ ^[Yy]$ ]] && want_dtz=1
  fi
  ((want_wdl)) || skip "declined at prompt"
  mkdir -p "$dest"
  need_gb=73; ((want_dtz)) && need_gb=161
  avail_gb="$(df -BG --output=avail "$dest" | tail -n1 | tr -dc '0-9')"
  log "free space at ${dest}: ${avail_gb} GB, need up to ${need_gb} GB (minus files already present)"
  if (( avail_gb < need_gb )) && [[ -z "$(ls -A "$dest" 2>/dev/null)" ]]; then
    err "not enough free disk space"; return 1
  fi
  syzygy_sha_list
  list="${PREFIX}/syzygy/6.sha256"
  if ((want_dtz)); then syzygy_list 6 6 > "$list"; else syzygy_list 6 6 | grep '\.rtbw$' > "$list"; fi
  syzygy_get "$dest" "$list" "$(lock_get syzygy-6-wdl 3)" "$(lock_get syzygy-6-dtz 3)"
  w="$(count_tb "$dest" rtbw)"; z="$(count_tb "$dest" rtbz)"
  note "${w} rtbw + ${z} rtbz, sha256 OK"
  [[ "$w" -eq 365 ]] && { ((want_dtz == 0)) || [[ "$z" -eq 365 ]]; }
}

step_perf() {
  CURRENT_STEP=perf
  # On WSL2 the /usr/bin/perf wrapper looks for tools matching the running kernel
  # (microsoft-standard-WSL2), which Ubuntu does not ship. Link the generic binary directly.
  local p
  if p="$(command -v perf 2>/dev/null)" && perf --version >/dev/null 2>&1; then
    :
  else
    p="$(ls -1d /usr/lib/linux-tools/*/perf 2>/dev/null | sort -V | tail -n1 || true)"
    [[ -n "$p" && -x "$p" ]] || { err "no perf binary under /usr/lib/linux-tools/*/ (is linux-tools-generic installed?)"; return 1; }
    ln -sf "$p" "${BIN}/perf"
    p="${BIN}/perf"
  fi
  "$p" --version
  note "$("$p" --version 2>&1 | head -n1); perf_event_paranoid=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo '?')"
}

step_valgrind() {
  CURRENT_STEP=valgrind
  valgrind --version
  note "$(valgrind --version)"
}

step_hotspot() {
  CURRENT_STEP=hotspot
  [[ "$FORK_TOOLS_HOTSPOT" == 1 ]] || skip "opt-in: rerun with FORK_TOOLS_HOTSPOT=1 (GUI; needs WSLg)"
  local url sha img
  url="$(lock_get hotspot-appimage 3)"; sha="$(lock_hash hotspot-appimage)"
  img="${PREFIX}/opt/hotspot.AppImage"
  mkdir -p "${PREFIX}/opt"
  fetch "$url" "$img" "$sha"
  chmod +x "$img"
  rm -rf "${PREFIX}/opt/hotspot"; mkdir -p "${PREFIX}/opt/hotspot"
  ( cd "${PREFIX}/opt/hotspot" && "$img" --appimage-extract >/dev/null )
  ln -sf "${PREFIX}/opt/hotspot/squashfs-root/AppRun" "${BIN}/hotspot"
  note "AppImage $(lock_get hotspot-appimage 2) extracted; run 'hotspot perf.data'"
}

print_manual_profilers() {
  cat <<'EOF'

Manual installs (licence acceptance required, not automated):
  * Intel VTune Profiler (EULA). Download page:
      https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html
    Options listed there: oneAPI apt repo (`sudo apt install intel-oneapi-vtune` after adding
    Intel's repo and key), offline/online .sh installer, Windows .exe, Docker image.
    Hardware event sampling inside WSL2 is UNVERIFIED; the Windows build may be the practical route.
  * AMD uProf 5.3 (EULA click-through on download): https://www.amd.com/en/developer/uprof.html
    Linux .deb/.rpm/.tar and Windows builds are offered there.
EOF
}

# ================================================================= main
main() {
  mkdir -p "$BIN" "$SRC" "$STAMPS" "${PREFIX}/downloads" "${PREFIX}/opt" "${PREFIX}/syzygy"
  rm -f "${STAMPS}"/*.note
  log "prefix: ${PREFIX}   lock: ${LOCK}   jobs: ${JOBS}"
  if ! grep -qi microsoft /proc/version 2>/dev/null; then
    warn "this does not look like WSL; the script was written for WSL2 Ubuntu but should work on Ubuntu"
  fi
  command -v apt-get >/dev/null || { err "apt-get not found: Ubuntu/Debian only"; exit 1; }

  run_step apt-deps      step_apt
  run_step fastchess     step_fastchess
  run_step cutechess-cli step_cutechess
  run_step ordo          step_ordo
  run_step syzygy-3-4-5  step_syzygy345
  run_step syzygy-6      step_syzygy6
  run_step perf          step_perf
  run_step valgrind      step_valgrind
  run_step hotspot       step_hotspot

  print_manual_profilers

  local name fails=0
  echo
  printf '%-15s %-5s %s\n' STEP RESULT NOTE
  printf '%-15s %-5s %s\n' ---- ------ ----
  for name in "${ORDER[@]}"; do
    printf '%-15s %-5s %s\n' "$name" "${RESULT[$name]}" "${NOTE[$name]:-}"
    [[ "${RESULT[$name]}" == FAIL ]] && fails=$((fails + 1))
  done
  echo
  echo "Add to your shell profile:  export PATH=\"${BIN}:\$PATH\""
  echo "Syzygy path for engines/fastchess -tb:  ${PREFIX}/syzygy/3-4-5$( [[ -d ${PREFIX}/syzygy/6 ]] && echo ":${PREFIX}/syzygy/6" )"
  if ((fails)); then
    err "${fails} step(s) failed; fix and rerun (finished steps are skipped)."
    exit 1
  fi
  log "all steps PASS or SKIP"
}

main "$@"
