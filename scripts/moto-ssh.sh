#!/usr/bin/env bash
# moto-ssh.sh — connect to the Moto G4 Plus playground over USB (ADB port-forward).
# Prereq on phone: open Termux and run `sshd` (listens on 8022). Not auto-started on boot.
set -euo pipefail

PHONE_USER="u0_a122"
KEY="$HOME/.ssh/id_moto_playground"
PORT=8022

# 1) Ensure a device is connected via adb.
if ! adb get-state >/dev/null 2>&1; then
  echo "No adb device. Plug in the phone (USB debugging authorized) and retry." >&2
  exit 1
fi

# 2) Set up the USB port-forward (idempotent).
adb forward tcp:${PORT} tcp:${PORT} >/dev/null
echo "USB forward active: localhost:${PORT} -> phone:${PORT}"

# 3) Connect (pass any args through to the remote shell, e.g. ./moto-ssh.sh 'uptime').
exec ssh -i "$KEY" -p "$PORT" \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
  "${PHONE_USER}@127.0.0.1" "$@"
