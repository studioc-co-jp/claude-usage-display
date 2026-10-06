# claude-usage-display

Claude Code の利用枠（5 時間・週次・Fable 週次）を、USB でつないだ 3.5 インチのディスプレイ（Turing Smart Screen rev A、`1a86:5722`）に表示する常駐プログラム。
概要と使い方は `README.md`、経緯・調べた事実（出典つき）・残っている作業は `docs/handover.md` にある。
リポジトリは会社の GitHub 組織に置いている（`git@github.com:studioc-co-jp/claude-usage-display.git`、private）。**作業を始める前に `docs/handover.md` の §5 を読む。**

## 規則

- 全体の規則は `~/.claude/CLAUDE.md`（GitHub `studioc-co-jp/studioc-claude-config`）に従う。ユーザーに見える文章は日本語・です/ます調で書く。README・コメント・ログの文言も日本語で書く
- **アクセストークンを画面・ログ・ファイル・commit に出さない。**例外の文言やデバッグ出力にも入れない。値を示す必要があるときは長さかマスク済みの形にする
- **Keychain のログイン情報（`Claude Code-credentials`）は読むだけで書かない。**リフレッシュトークンも使わない。更新結果を書き戻すと Claude Code のログインが壊れる（junhoyeo/tokscale #1001）
- 利用枠 API の生の応答をリポジトリに入れない。fixtures には使う項目だけを残す。トップレベルにある用途不明の項目（社内コード名に見える名前）は、fixtures にも記事にも載せない
- **GPL-3.0 のコード（`mathoudebine/turing-smart-screen-python` と gist `amarok30/cddaa9a9…`）を流用しない。**使ってよいのは仕様（コマンド番号・バイト配置・転送の規則）だけで、コードは自前で書く
- macOS ではシリアル（`/dev/cu.usbmodem…`）で送らない。`claude_usage_display/turing.py` の docstring にある 4 つの規則（コマンドは 1 転送ずつ・`SET_ORIENTATION` は 11 バイト・画素は 64 バイトの倍数で区切る・画素の途中にほかを書かない）を崩さない
- 記事はこのリポジトリに置かない。`~/projects/studioc` で起動したセッションが `/techblog-write` で書く。素材（調べた事実と出典、実機で分かったこと）は `docs/article-material.md` に残す。実機で分かったことは同文書の §10 に追記する
- commit は `git commit --only -m "…" -- <パス>` で行う。新規ファイルは先に `git add <そのパス>`。`git add -A` / `git add .` は使わない（hook が止める）
- **commit の作成者のメールアドレスは、GitHub の非公開用アドレスにする。**このリポジトリだけ `git config --local user.email "75772838+blacksawa@users.noreply.github.com"` を設定してある（clone し直したら設定し直す）。commit の前に `git config user.email` を確かめる。個人のメールアドレスは、ファイルにも commit メッセージにも書かない（2026-10-05 に履歴を書き換えて消した。経緯は `docs/handover.md` §6）

## 開発

```
.venv/bin/python -m unittest discover -s tests                     # 単体テスト
.venv/bin/python -m claude_usage_display preview --demo -o demo.png # ディスプレイ無しで画面を確かめる
```

- 依存は `requirements.txt`（版を固定）。libusb は Homebrew で入れる
- 画面は 2 種類ある。既定のゲージ型は `claude_usage_display/gauge.py`、横棒の画面（`--theme classic`）は `claude_usage_display/render.py`。ユーザーがゲージ型を選んだうえで、戻せるように横棒の画面を残している（2026-10-05）
- 画面の色は、送る前に RGB565 へ落ちる。中間の灰色は緑に寄るので、新しい灰色を足すときは RGB565 でそのまま表せる値にする（`tests/test_gauge.py` の `test_card_color_survives_rgb565`）
- README の画像（`docs/images/`）は `preview --demo` で作る。実際の利用枠が写った画像は commit しない
- 自動起動のひな形は `launchd/`、登録・解除は `scripts/` にある
