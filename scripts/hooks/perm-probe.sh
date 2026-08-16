#!/bin/sh
# PermissionRequest payload를 그대로 남긴다. 무엇이 오는지 보려는 것이라
# 해석하지 않는다. 승인 여부에는 관여하지 않는다.
set -u
payload="$(cat 2>/dev/null || true)"
mkdir -p "$HOME/.dispatch" 2>/dev/null || true
printf '%s\n' "{\"at\":\"$(date -u +%H:%M:%S)\",\"payload\":$payload}" >> "$HOME/.dispatch/perm.jsonl" 2>/dev/null || true
echo '{}'
