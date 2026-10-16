#!/bin/sh
# 自動起動（launchd の LaunchAgent）を登録する。登録し直すときも同じコマンドを実行する。
#
#   scripts/install-launch-agent.sh [run のオプション…]
#   scripts/install-launch-agent.sh --monitor [monitor のオプション…]   サーバーの状態の画面（別の常駐）
#   scripts/install-launch-agent.sh --local [local のオプション…]       この Mac の状態の画面（別の常駐）
#   例: scripts/install-launch-agent.sh --flip --brightness 40
#       scripts/install-launch-agent.sh --monitor --device 3.5
#       scripts/install-launch-agent.sh --local --location 0x00112000
#
# launchd/ のひな形のパスを置き換えて ~/Library/LaunchAgents/ に置き、読み込ませる。
# run・monitor・local は別のラベル・別のログで、同時に登録できる（ディスプレイは --device で分ける。
# 3.5 インチを 2 台使うときは、monitor と local の両方に --location を付けて、USB の位置で分ける）。
set -eu

LABEL=jp.co.studioc.claude-usage-display
COMMAND=run
LOG="$HOME/Library/Logs/claude-usage-display.log"
if [ "${1:-}" = "--monitor" ]; then
  shift
  LABEL=jp.co.studioc.claude-usage-display.monitor
  COMMAND=monitor
  LOG="$HOME/Library/Logs/claude-usage-display-monitor.log"
elif [ "${1:-}" = "--local" ]; then
  shift
  LABEL=jp.co.studioc.claude-usage-display.local
  COMMAND=local
  LOG="$HOME/Library/Logs/claude-usage-display-local.log"
fi
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
PYTHON="$ROOT/.venv/bin/python"
TEMPLATE="$ROOT/launchd/jp.co.studioc.claude-usage-display.plist"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ ! -x "$PYTHON" ]; then
  echo "$PYTHON がありません。README の「準備」の手順で .venv を作ってください" >&2
  exit 1
fi

cd "$ROOT"

# オプションの誤りは登録する前に止める（登録後に誤ると、launchd が 10 秒ごとに起動し直し続ける）。
# 本物の引数解析を通し、コマンドの本体だけを差し替えて起動はしない。monitor は設定ファイルも読んで確かめる。
# --help（-h・--he などの省略形も）は説明を出すだけで登録しない。引数解析は説明を出すと 0 で終わるため、
# 誤りなしと区別できず、2026-10-16 に run --help が常駐として登録された（利用枠の画面が一晩止まった）。
status=0
"$PYTHON" - "$COMMAND" "$@" <<'EOF' || status=$?
import sys

import claude_usage_display.__main__ as cli


def check_monitor(args):
    try:
        cli.load_config(args.config)
    except cli.ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


cli.cmd_run = lambda args: 0
cli.cmd_monitor = check_monitor
cli.cmd_local = lambda args: 0
try:
    code = cli.main(sys.argv[1:])
except SystemExit as e:
    # 誤りは 2 で終わる。0 で終わるのは、コマンドの本体まで進まずに説明を出したとき
    sys.exit(3 if e.code in (0, None) else e.code)
sys.exit(code)
EOF
if [ "$status" -eq 3 ]; then
  echo "説明を表示しただけで、登録は変えていません" >&2
  exit 0
fi
[ "$status" -eq 0 ] || exit "$status"

mkdir -p "$(dirname "$TARGET")" "$(dirname "$LOG")"
TMP=$(mktemp "${TARGET}.XXXXXX")
trap 'rm -f "$TMP"' EXIT

"$PYTHON" - "$TEMPLATE" "$TMP" "$PYTHON" "$ROOT" "$LOG" "$LABEL" "$COMMAND" "$@" <<'EOF'
import sys
from xml.sax.saxutils import escape

template, out, python, root, log, label, command, *options = sys.argv[1:]
text = open(template, encoding="utf-8").read()
text = text.replace("@PYTHON@", escape(python)).replace("@ROOT@", escape(root)).replace("@LOG@", escape(log))
text = text.replace("@LABEL@", escape(label)).replace("@COMMAND@", escape(command))
text = text.replace(
    "    <!-- @RUN_OPTIONS@ -->\n",
    "".join(f"    <string>{escape(option)}</string>\n" for option in options),
)
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
EOF
plutil -lint -s "$TMP"

# DRY_RUN=1 のときは、作った plist を表示して終わる（登録しない。確かめる用）
if [ "${DRY_RUN:-}" = 1 ]; then
  cat "$TMP"
  exit 0
fi

# 読み込み済みなら外してから置き換える（外し終わる前に読み込むと失敗するため、消えるまで待つ）
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
  i=0
  while launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 30 ]; then
      echo "以前の登録を外せません（launchctl print $DOMAIN/$LABEL を確かめてください）" >&2
      exit 1
    fi
    sleep 1
  done
fi

chmod 644 "$TMP"
mv "$TMP" "$TARGET"
launchctl bootstrap "$DOMAIN" "$TARGET"

echo "登録しました: $TARGET"
echo "ログ: $LOG"
sleep 2
# 最上位の行（タブ 1 つの字下げ）だけを出す
launchctl print "$DOMAIN/$LABEL" | grep -E "^$(printf '\t')(state|pid|last exit code) =" || true
