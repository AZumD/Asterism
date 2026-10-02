#!/usr/bin/env bash
# Diagnose Asterism nested Plasma display env for Desktop Settings launch.
set -euo pipefail
uid=$(id -u)
rt=/run/user/$uid
echo "=== sockets under $rt ==="
ls -la "$rt"/wayland* 2>/dev/null || true
ls -la "$rt"/asterism_nested 2>/dev/null || true
find "$rt" -maxdepth 3 \( -name 'wayland-*' -o -name '*.env' -o -name 'bus' \) 2>/dev/null | head -40
echo "=== plasmashell environ ==="
ps -u "$(id -un)" -o pid=,cmd= | while read -r pid cmd; do
  case $cmd in
    *plasmashell*) echo "PID $pid $cmd"; tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | grep -E '^(WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|XAUTHORITY)=' || true ;;
  esac
done
echo "=== kwin environ ==="
ps -u "$(id -un)" -o pid=,cmd= | while read -r pid cmd; do
  case $cmd in
    *kwin_wayland\ *) echo "PID $pid"; tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | grep -E '^(WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|XAUTHORITY)=' || true ;;
  esac
done
echo "=== frametop plasmashell.env if any ==="
ls -la "$rt"/frametop 2>/dev/null || true
