#!/bin/sh
# 自動起動（launchd の LaunchAgent）を解除する。ログ（~/Library/Logs/claude-usage-display.log）は残す。
set -eu

LABEL=jp.co.studioc.claude-usage-display
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  # run は SIGTERM を受けると、送信の途中で止めずに終わる。bootout は終わるのを待たずに戻るため、消えるまで待つ
  launchctl bootout "$DOMAIN/$LABEL"
  i=0
  while launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 30 ]; then
      echo "停止を待ちきれません（launchctl print $DOMAIN/$LABEL を確かめてください）" >&2
      exit 1
    fi
    sleep 1
  done
  echo "停止しました"
fi
rm -f "$TARGET"
echo "解除しました"
