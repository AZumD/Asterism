#!/usr/bin/env bash
# Shared helpers: capture / load nested Asterism plasmashell environment safely (no eval).
# Pattern from FrameTop session/ft-shell-env.sh (https://github.com/AZumD/frametop) —
# adapted for XDG_RUNTIME_DIR=…/asterism_nested instead of …/frametop.

asterism_shell_env_keep() {
  case $1 in
    HOME|USER|LOGNAME|PATH|LANG|LANGUAGE|SHELL|DISPLAY|SESSION_MANAGER|DESKTOP_SESSION|TERM|TZ)
      return 0 ;;
    XDG_*|DBUS_*|WAYLAND_*|QT_*|KDE_*|KWIN_*|PLASMA_*|LC_*|KS*|GSM_*|GDK_*|GTK_*|PAM_*|XAUTH*)
      return 0 ;;
    *) return 1 ;;
  esac
}

asterism_nested_runtime() {
  echo "${XDG_RUNTIME_DIR_HOST:-/run/user/$(id -u)}/asterism_nested"
}

asterism_shell_env_path() {
  echo "$(asterism_nested_runtime)/plasmashell.env"
}

# True if pid looks like nested Asterism plasmashell (wayland-N + …/asterism_nested).
asterism_shell_env_pid_is_nested() {
  local pid=$1 runtime=no wayland=no line
  [ -r "/proc/$pid/environ" ] || return 1
  while IFS= read -r line; do
    case $line in
      XDG_RUNTIME_DIR=*/asterism_nested) runtime=yes ;;
      WAYLAND_DISPLAY=wayland-[0-9]*) wayland=yes ;;
    esac
  done < <(tr '\0' '\n' < "/proc/$pid/environ")
  [ "$runtime" = yes ] && [ "$wayland" = yes ]
}

asterism_find_nested_plasmashell() {
  local pid
  for pid in $(pgrep -x plasmashell 2>/dev/null || true); do
    if asterism_shell_env_pid_is_nested "$pid"; then
      echo "$pid"
      return 0
    fi
  done
  return 1
}

# Write NUL-separated env from /proc/$pid/environ → $dest (atomic).
asterism_shell_env_capture() {
  local pid=$1 dest=$2
  local proc_env=$dest.tmp.$$
  local runtime_ok=0 wayland_ok=0
  [ -r "/proc/$pid/environ" ] || return 1
  mkdir -p "$(dirname "$dest")"
  : > "$proc_env"
  while IFS= read -r -d '' entry; do
    case $entry in
      *=*) ;;
      *) continue ;;
    esac
    local k=${entry%%=*}
    local v=${entry#*=}
    [[ $k =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    asterism_shell_env_keep "$k" || continue
    case $k in
      XDG_RUNTIME_DIR)
        case $v in */asterism_nested) runtime_ok=1 ;; esac ;;
      WAYLAND_DISPLAY)
        case $v in wayland-0|wayland-[0-9]*) wayland_ok=1 ;; esac ;;
    esac
    printf '%s=%s\0' "$k" "$v" >> "$proc_env"
  done < "/proc/$pid/environ"
  if [ "$runtime_ok" != 1 ] || [ "$wayland_ok" != 1 ]; then
    rm -f "$proc_env"
    return 1
  fi
  mv -f "$proc_env" "$dest"
  return 0
}

# Load NUL-separated env file into the current shell (exports). No eval.
asterism_shell_env_load() {
  local file=$1
  local entry k v
  [ -f "$file" ] || return 1
  while IFS= read -r -d '' entry; do
    case $entry in
      *=*) ;;
      *) continue ;;
    esac
    k=${entry%%=*}
    v=${entry#*=}
    [[ $k =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    asterism_shell_env_keep "$k" || continue
    printf -v "$k" '%s' "$v"
    export "$k"
  done < "$file"
  return 0
}

# Ensure current shell has nested Plasma display env (SSH / plain tty safe).
asterism_shell_env_attach() {
  local rt nested_rt envfile pid
  rt=/run/user/$(id -u)
  nested_rt=$rt/asterism_nested
  envfile=$nested_rt/plasmashell.env

  # Already inside nested Plasma (menu / Konsole on desktop).
  case ${XDG_RUNTIME_DIR:-} in
    */asterism_nested)
      case ${WAYLAND_DISPLAY:-} in
        wayland-[0-9]*|/*)
          return 0 ;;
      esac
      ;;
  esac

  if pid=$(asterism_find_nested_plasmashell 2>/dev/null); then
    asterism_shell_env_capture "$pid" "$envfile" || true
  fi

  if [ -f "$envfile" ]; then
    asterism_shell_env_load "$envfile" || return 1
  else
    return 1
  fi

  case ${WAYLAND_DISPLAY:-} in
    wayland-[0-9]*) ;;
    *) return 1 ;;
  esac
  case ${XDG_RUNTIME_DIR:-} in
    */asterism_nested) ;;
    *) return 1 ;;
  esac

  # Resolve relative Wayland socket under nested runtime for backends that need it.
  local wl=$WAYLAND_DISPLAY
  case $wl in
    /*) ;;
    *)
      if [ -S "$XDG_RUNTIME_DIR/$wl" ]; then
        :
      else
        return 1
      fi
      ;;
  esac
  return 0
}
