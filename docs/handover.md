# 引き継ぎ: claude-usage-display（2026-10-05 作成）

`~/projects/studioc` で起動したセッションが、ここまで作った。以降は、このディレクトリで起動したセッションが引き継ぐ。
**このファイルを最初に読み、「残っている作業」を上から順に片付ける。**

## 1. 目的

Claude Code の利用枠 3 つ（**5 時間・週次・Fable 週次**）を、Mac に USB でつないだ 3.5 インチディスプレイにメーターで常時表示する。
完成したら、studioc.co.jp のテックブログ（`/tech`）で公開する。記事は `~/projects/studioc` で起動したセッションが `/techblog-write` で書く。
このリポジトリには記事を置かない。

きっかけ: nuits_jp さんの X 記事「AI専用ダッシュボードの作り方」（https://x.com/nuits_jp/status/2106686059509883050 、2026-10-04）。

## 2. 決まっていること

| 項目 | 決定 | 根拠 |
|---|---|---|
| 機種 | Turing Smart Screen 3.5 インチ（rev A、USB `1a86:5722`、シリアル `USB35INCHIPSV2`）。AliExpress の TURZX 品（商品 ID 1005008850981488）。**未着** | 商品画像の付属ソフト画面（ウィンドウ名 `Turing Smart Screen`、Screen Flip・Theme・Brightness）が rev A の付属ソフトと一致 |
| 画面 | 480×320 の横向き。**ゲージ型（カード 3 枚に円形ゲージ）が既定。**最初に作った横棒の画面は `--theme classic` で残す | ユーザーが選択（2026-10-05。経緯は §4-5） |
| 言語 | Python 3（Homebrew の python3 3.14）、Pillow 12.3.0、pyusb 1.3.1、Homebrew の libusb | 手元で動作確認済み |
| 利用枠の取得 | Keychain の `Claude Code-credentials` からアクセストークンを読み、`GET https://api.anthropic.com/api/oauth/usage`（ヘッダー `anthropic-beta: oauth-2025-04-20`）を 2 分ごとに呼ぶ | 2026-10-05 にこの Mac で HTTP 200 を確認（§4） |
| 送信方式 | **シリアル（`/dev/cu.usbmodem…`）を使わず、libusb でバルク OUT `0x03` に直接書く** | macOS ではシリアル経由だと画像が崩れる（§4） |
| 記事 | 完成後、studioc で `/techblog-write` | studioc の `CLAUDE.md` §3 |

## 3. 現在の状態

2026-10-05 夕方、このディレクトリで起動したセッションが §5 の 1〜5 を終えた時点の状態。

- **GitHub `studioc-co-jp/claude-usage-display`（private）の `main` に push 済み。**2026-10-05 に作成者のメールアドレスを非公開用に書き換えるため、GitHub 上のリポジトリを作り直して push し直し、そのあと会社の組織 `studioc-co-jp` へ移した（§6）
- **自動起動は登録済み**（2026-10-05、既定のオプション。`~/Library/LaunchAgents/jp.co.studioc.claude-usage-display.plist`）。ディスプレイが無いので `run` は待機中で、API は呼んでいない。ログは `~/Library/Logs/claude-usage-display.log`
  - 登録・オプションを変えての登録し直し・誤ったオプションの拒否・解除・強制終了後の起動し直し（約 3 秒）を実際に動かして確かめた
  - launchd から起動しても Keychain の読み取りと利用枠の取得が通ることを、`preview` を 1 回だけ動かす使い捨てのジョブで確かめた（§4-6）
- テストは 49 件すべて成功（`.venv/bin/python -m unittest discover -s tests`）
- この回で見つけて直した不具合（いずれもテストを追加済み）
  - `--brightness` の範囲外（例: 150）が引数解析を通り、接続した時点で初期化の失敗を 10 秒ごとに繰り返す → 引数解析で止める
  - 取得失敗の文言のうち最長の「ログイン切れ（…）」が、時刻と合わせて右端で切れる → 理由と時刻を左右に分け、収まらないときは文字を縮める
  - 最初の取得に失敗したとき、`--model` に関係なく見出しが「Fable週次」になる → `usage.meter_labels()` で名前を 1 か所で決める
- **`gh` は、この組織のリポジトリ専用のトークンを `GH_TOKEN` で渡して使う。**保存済みの `gh` のログイン（`blacksawa` の fine-grained トークン、キーチェーン）は、持ち主が `blacksawa` なので組織のリポジトリは見えない（1 つのトークンが使えるのは 1 人か 1 つの組織の持ち物だけ。GitHub の文書「Managing your personal access tokens」）。ほかのセッションもそのログインを使うので、`gh auth login` で入れ替えない
  - 組織用のトークン: 持ち主 `studioc-co-jp`、対象は `claude-usage-display` だけ、権限は Administration（読み書き）と Contents（読み取り）、期限 90 日（2026-10-05 作成）。キーチェーンの項目 `gh-token-studioc-co-jp`（アカウント `blacksawa`）に入れてある
  - 使い方: `GH_TOKEN=$(security find-generic-password -s gh-token-studioc-co-jp -w) gh repo view studioc-co-jp/claude-usage-display`。2026-10-05 にこの形で読み取りと、Administration の権限が要る読み取り（デプロイキーの一覧）が通ることを確かめた
  - 期限が切れたら、同じ条件で作り直し、`security add-generic-password -U -a blacksawa -s gh-token-studioc-co-jp -w` で入れ替える
  - **push は SSH の remote で行う**（`git@github.com:studioc-co-jp/claude-usage-display.git`）
- `.venv/` は `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` で作れる（2026-10-05 に新しい venv で作り、テストが通ることを確認）
- ディスプレイ未接続の状態で、`run` が「接続を待っています」と記録して待機し、SIGTERM で正常に終わることを確認済み

### ファイル

| パス | 役割 |
|---|---|
| `claude_usage_display/usage.py` | Keychain からトークンを読み、利用枠 API を呼び、`limits` 配列から 3 本を取り出す |
| `claude_usage_display/gauge.py` | 既定の画面（ゲージ型）を描く |
| `claude_usage_display/render.py` | 横棒の画面（`--theme classic`）と、画面に共通の部品（フォント、リセット時刻の書式）。確認画面（`render_test_pattern`）もここにある |
| `claude_usage_display/turing.py` | rev A のコマンド組み立て、RGB565（リトルエンディアン）への変換、libusb での送信 |
| `claude_usage_display/__main__.py` | `preview` / `probe` / `test-pattern` / `run` の 4 コマンド。`run` は常駐ループ |
| `tests/` | 単体テスト 49 件。`fixtures/usage_response.json` は実際の応答から必要な項目だけを残したもの |
| `launchd/jp.co.studioc.claude-usage-display.plist` | 自動起動のひな形（`@…@` をパスに置き換えて使う） |
| `scripts/install-launch-agent.sh` / `uninstall-launch-agent.sh` | 自動起動の登録（登録し直し）と解除 |
| `README.md` / `CLAUDE.md` | 使い方と、このリポジトリで作業するときの規則 |
| `docs/images/` | README の画像（`preview --demo` の見本の値。実際の利用枠は載せない） |

使い方:

```
.venv/bin/python -m claude_usage_display preview -o preview.png   # 実際の値で画像だけ作る
.venv/bin/python -m claude_usage_display preview --demo -o demo.png  # API を呼ばず見本の値で描く
.venv/bin/python -m claude_usage_display probe                    # ディスプレイの USB 情報とインターフェース確保の可否
.venv/bin/python -m claude_usage_display test-pattern             # 向きと色の確認画面（左上が赤で「左上」）
.venv/bin/python -m claude_usage_display run                      # 常駐（--brightness 30 --interval 120 --flip --save-png --theme）
scripts/install-launch-agent.sh [run のオプション]                 # 自動起動の登録（登録し直し）
scripts/uninstall-launch-agent.sh                                 # 自動起動の解除
```

## 4. 調べて分かったこと（記事の素材。出典つき）

### 4-1. 記事で紹介されている token-dashboard は Mac では使えない

- `nuitsjp/token-dashboard`（MIT、Go）は **Windows 11 と TURZX 9.2 インチ（`1CBE:0092`）専用**。「Windows 以外の OS」「9.2 インチ以外の機種」は対象外と明記（同リポジトリ `docs/project.md` 12・16 行目）
- 配布物は Windows 用の `token-monitor-turzx-0.1.6-amd64-setup.exe` だけ（v0.1.6、2026-10-04）
- 9.2 インチは USB バルク転送で、DES-CBC（鍵 `slv3tuzx`）で暗号化した 512 バイトのヘッダーと JPEG/PNG を送る方式。**3.5 インチ rev A とは通信方式がまったく違う**

### 4-2. 利用枠 API の応答（2026-10-05 にこの Mac で取得）

- tokscale（`junhoyeo/tokscale`、MIT、Rust）の `crates/tokscale-cli/src/commands/usage/claude.rs` と同じ呼び方（18 行目 `USAGE_URL`、412〜415 行目のヘッダー）
- Keychain の読み取りで確認画面は出なかった。ログイン情報の `subscriptionType` は `max`、`rateLimitTier` は `default_claude_max_5x`
- `limits` 配列に 3 件あった。**Fable 週次は `kind: "weekly_scoped"`、`scope.model.display_name: "Fable"`（`id` は null）で返る**

| kind | group | 当時の値 | 表示名 |
|---|---|---|---|
| `session` | session | 26%（`is_active: true`） | 5時間 |
| `weekly_all` | weekly | 3% | 週次 |
| `weekly_scoped` | weekly | 0%（model `Fable`） | Fable週次 |

- 各要素に `severity`（観測値は `normal` だけ）と `is_active`（いま効いている枠が 1 つだけ true）がある。色はこの `severity` を使わず、自前のしきい値（70% で注意色、90% で危険色）で決めている。`normal` 以外の値を観測できていないため
- 旧来の `five_hour` / `seven_day`（`utilization`）も返る。`seven_day_opus` / `seven_day_sonnet` は null だった。トップレベルには用途不明の項目が多数ある。社内コード名と見られる名前が並ぶため、**fixtures にも記事にも載せない**
- **トークンは読むだけで、リフレッシュしない。**tokscale は更新結果を書き戻して Claude Code のログインを壊した（`claude.rs` 265〜273 行目のコメント、tokscale #1001）。期限切れ（401/403）のときは「ログイン切れ（Claude Code を起動すると戻ります）」と表示する

### 4-3. macOS ではシリアル経由だと画像が崩れる

- `mathoudebine/turing-smart-screen-python`（GPL-3.0）の README は macOS に「major bug」の注記を付けており、issue #7「Screen displays corrupted images on Mac」は 2022 年から open のまま
- issue #7 のコメント（amarok30、Mac mini M4・macOS 26.5.2・`1a86:5722`・`USB35INCHIPSV2` で検証）で原因と回避策が示された
  - パネルのファームウェアは **USB 転送の単位で動く**。転送の先頭からコマンドを読み、その転送の残りは捨てる
  - `DISPLAY_BITMAP` の後は、幅×高さ×2 バイトの画素を数え終えるまで、届いたものをすべて画素として扱う
  - macOS の CDC ドライバーは、転送を任意に分割・結合する。そのためコマンドが画素に混ざり、一度ずれると電源を入れ直すまで崩れ続ける
  - 回避策: libusb でバルク OUT `0x03`（インターフェース 1）に直接書く。コマンドは 1 つずつ別の転送で送り、`SET_ORIENTATION` は 11 バイトにする。画素は 64 バイトの倍数で区切り、合計をちょうど幅×高さ×2 バイトにする。画素を送っている途中に、ほかのものを書かない
  - 実装: https://gist.github.com/amarok30/cddaa9a9818d6830a74d9332f501047e （GPL-3.0）
  - 同じ挙動の記述: `tanakamasayuki/EspUsbHost` の `examples/Serial/EspUsbHostDisplayTuring/TuringDevice.hpp`
- **GPL-3.0 のコードは流用していない。**コマンド番号・バイト配置・転送の規則という「仕様」だけを使い、`turing.py` は自前で書いた。公開するときもこの線を守る

### 4-4. rev A の仕様（`lcd_comm_rev_a.py` から）

- コマンド: RESET 101、CLEAR 102、SCREEN_OFF 108、SCREEN_ON 109、SET_BRIGHTNESS 110、SET_ORIENTATION 121、DISPLAY_BITMAP 197
- 6 バイトの形式: x・y・ex・ey を 10 ビットずつ詰め、最後の 1 バイトがコマンド番号
- 向き: PORTRAIT 0、REVERSE_PORTRAIT 1、LANDSCAPE 2、REVERSE_LANDSCAPE 3（送る値は +100）。横向きでは幅 480・高さ 320
- 明るさ: 0 が最も明るく 255 が最も暗い（`255 - 割合×255/100`）
- 画素: RGB565 のリトルエンディアン。Pillow の組み込み変換（`BGR;16` 等）は RGB から使えないため手計算（480×320 で約 0.04 秒）

### 4-5. 画面のデザイン（2026-10-05）

- 経緯: 最初の横棒の画面を見たユーザーが「全体的にいい感じだが、もう少しおしゃれに。元に戻す可能性がある前提で、Apple のデザインパターンを参考に」と依頼。A（設定アプリのグループ化リスト風）と B（ウィジェットのバッテリー風の円形ゲージ）の 2 案を作り、**B を採用**。続けて「カード内の要素が上に寄っている → 縦の中央に」「『あと◯時間』と上の要素の隙間を空け、そのうえで中央に」の 2 点を直した。横棒の画面は `--theme classic` で残した
- 色は HIG の Color（https://developer.apple.com/design/human-interface-guidelines/color 。ページのデータ `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/color.json` から取得。2025-06-09 に値が更新された版）のダークモードの値

  | 用途 | HIG の名前 | Default (dark) |
  |---|---|---|
  | 通常（70% 未満） | Blue | 0, 145, 255 |
  | 注意（70% 以上） | Orange | 255, 146, 48 |
  | 危険（90% 以上） | Red | 255, 66, 69 |
  | 補足の文字 | Gray | 142, 142, 147 |
  | さらに控えめな文字 | Gray (2) | 99, 99, 102 |
  | カードの面 | Gray (6) | 28, 28, 30 → **33, 32, 33 に置き換え**（下記） |

- **RGB565 では中間の灰色が緑に寄る。**赤・青は 5 ビット、緑は 6 ビットなので、Gray (6) の (28, 28, 30) は (24, 28, 24) になる（送信データを画像に戻して確認）。RGB565 でそのまま表せる無彩色のうち、液晶で黒地との差が見えやすい明るい側 (33, 32, 33) を使い、テストで固定した
- 文字の大きさは HIG の Typography（https://developer.apple.com/design/human-interface-guidelines/typography 、「iOS, iPadOS Dynamic Type sizes」の Large (default)）の pt をそのままピクセルで使った。Title 1 28・Headline 17・Subhead 15・Footnote 13・Caption 1 12
  - 根拠: iPhone 3GS の技術仕様（https://support.apple.com/kb/SP565）に「3.5-inch (diagonal) … 480-by-320-pixel resolution at 163 ppi」とある。このパネルも 3.5 インチ・480×320（計算で約 165 ppi）なので、iPhone で見る文字とほぼ同じ物理的な大きさになる
- 数字は SF Pro Rounded（`/System/Library/Fonts/SFNSRounded.ttf`。太さの軸を持つ可変フォントで、Pillow の `set_variation_by_name("Semibold")` で太さを選ぶ）。日本語はヒラギノ角ゴシック。この Mac の Pillow は raqm が有効（`features.check("raqm")` が True）
- 図形は 4 倍で描いて LANCZOS で縮め、文字は縮めた後に等倍で書く（縮めると文字がかすれるため）。描画と RGB565 への変換は 1 回 38 ミリ秒
- 時刻は iOS の日本語表記にならい、時の先頭に 0 を付けない（「9:55」）

### 4-6. launchd で分かったこと（2026-10-05、macOS 27.0.1）

- launchd は `LANG`・`LC_ALL` を渡さない。Python 3.14 は C ロケールで UTF-8 モードに自動で入る（launchd 経由で `sys.flags.utf8_mode = 1`、`sys.stderr.encoding = utf-8` を確認）。plist では `PYTHONUTF8=1` を明示している
- launchd から `security find-generic-password` で Keychain を読んでも確認画面は出ず、利用枠の取得まで通った（使い捨てのジョブで `preview` を動かし、終了コード 0）
- **`launchctl bootout` はサービスの終了を待たずに戻る。**直後の `launchctl print` ではまだ読み込まれており、プロセスも残っていた。登録・解除のスクリプトは、`launchctl print` が失敗する（消える）まで待つ
- `KeepAlive` が true なので、`kill -9` で落としても約 3 秒で起動し直した
- macOS 27 の `system_profiler` には `SPUSBDataType` が無く、`SPUSBHostDataType` を使う（`system_profiler -listDataTypes` で確認）

## 5. 残っている作業（上から順に）

1〜5 は 2026-10-05 に終えた（README.md、CLAUDE.md、requirements.txt と .gitignore、自動起動の作成と登録、git の初期化と push）。

6. **ディスプレイが届いたら**（外部要因。到着が再開の条件）
   1. **先に自動起動を止める**（`scripts/uninstall-launch-agent.sh`）。登録したままつなぐと、常駐の `run` がすぐに送信を始め、`probe`・`test-pattern` と同じパネルへ同時に書くことになる。パネルは画素を数えながら受け取るので、2 つのプロセスが書くと画面が崩れる（§4-3）
   2. USB-C でつなぎ、`system_profiler SPUSBHostDataType | grep -B8 -A2 'USB Product ID: 0x5722'` で `1a86:5722` と**シリアル番号 `USB35INCHIPSV2`** が見えるかを確かめる。別の ID なら rev A ではないので、§4-3・§4-4 の前提から見直す。**ID が同じでもシリアルが `2017-2-25` なら XuanFang の rev B で、通信方式が違う**（`lcd_comm_rev_b.py` 75・77 行目。rev A は同 72・74 行目）。`turing.py` はシリアルを見ずに ID だけで開くので、この確認は `probe` より前に手で行う（`probe` も `serial_number` を表示する）
   3. `probe` で、インターフェース 1 を確保できるかを確かめる。macOS の CDC ドライバーが握っていて確保できない場合は、その時のエラーをもとに対処を調べる（gist の報告者は確保できている）
   4. `test-pattern` で向きと色を確かめる。上下が逆なら `--flip` を付ける。赤と青が入れ替わっていたら RGB565 の並びを見直す
   5. `run --save-png /tmp/last.png` を数分動かし、画面と保存画像が一致することを確かめる。ゲージ型の細部（リングの縁、灰色の文字の読みやすさ、カードの面と黒地の差）を実機で見て、ユーザーに見てもらう。合わなければ `--theme classic` と見比べる
   6. 自動起動を登録し直す（上下が逆なら `scripts/install-launch-agent.sh --flip`）。ログアウト・ログインのあとも表示されることを確かめる
7. 実機で分かったこと（確保の可否、向き、明るさ、転送にかかる時間、ゲージ型の見え方）を、§4 に追記する

## 6. 公開するときに確かめること

- **認証の扱い（2026-10-05 に調査。公開の可否を左右する）**: このツールは、Claude Code が Keychain に置いた OAuth のアクセストークンを読み、文書化されていない `/api/oauth/usage` を呼ぶ。Claude Code の「Legal and compliance」（https://code.claude.com/docs/en/legal-and-compliance 、「Authentication and credential use」）は次のように定める
  - OAuth 認証は、サブスクリプションの購入者が Claude Code と Anthropic 純正のアプリを普通に使うためのもの（"designed to support ordinary use of Claude Code and other native Anthropic applications"）
  - 製品やサービスを作る開発者は API キーを使う。第三者の開発者が、Free・Pro・Max の資格情報で利用者の代わりにリクエストを流すことは認めない。開発者は Claude.ai の資格情報やセッショントークンを収集・保存・仲介してはならない
  - Anthropic は、これらの制限を予告なく執行できる（"may do so without prior notice"）。用途ごとの可否は sales への問い合わせを案内している
  - このツールは、利用者本人の Mac で本人のトークンを読むだけで、保存も他人への提供もしない。ただし、Anthropic 純正ではないアプリが OAuth のトークンを使う点について、上の文書は許可も禁止も明示していない
  - 公式に渡される別の経路がある: ステータスラインのスクリプトに渡る JSON の `rate_limits.five_hour` / `rate_limits.seven_day`（`used_percentage` と `resets_at`）。https://code.claude.com/docs/en/statusline の「Rate limit usage」。**モデル別の週次（Fable 週次）は含まれない。**Claude Code のセッションが動いているあいだだけ更新される（`refreshInterval` で定期的に更新できる）
- **commit の作成者欄のメールアドレスは公開しない**（2026-10-05 ユーザーが決定）。GitHub のユーザー `blacksawa` の公開リポジトリは 0 件（認証なしの API で確認）で、public にすれば、commit の作成者欄に入っていた個人のメールアドレスが初めて公開されるため
  - このリポジトリの `user.email` は非公開用アドレス `75772838+blacksawa@users.noreply.github.com` にした（`git config --local`。全体の設定は変えていない）。形式は GitHub の文書「Email addresses reference」の「Your noreply email address」（2017-07-18 より後に作ったアカウントは `ID+USERNAME@users.noreply.github.com`。`blacksawa` は 2020-12-10 作成、ID 75772838）
  - 既存の commit は `git filter-repo --mailmap` で書き換えた（日時とツリーは変わらない。`origin` の設定が消えるので登録し直した）。この文書の中に書いていたアドレスも `git filter-repo --replace-text` で履歴から消した。**個人のアドレスを、ファイルにも commit メッセージにも書かない**
  - 強制 push では古い commit が GitHub に残る（「Removing sensitive data from a repository」に、SHA-1 を指定すればキャッシュから見られると書かれている。GitHub Support は機微でないデータの削除に応じない）。そのため **GitHub 上のリポジトリを削除して作り直し、書き換えた履歴を push した**（2026-10-05。作り直しはユーザーが GitHub の画面で行った）
- **リポジトリは会社の GitHub 組織 `studioc-co-jp`（表示名 studio C）に置く**（2026-10-05 ユーザーが決定・作成）
  - 理由: LICENSE の名義が会社で、記事も studioc.co.jp に載せるため。GitHub の規約（Terms of Service「A. Definitions」）で、組織は「1 つの法人に結び付けられる共有の作業場所」とされる。会社名義の個人アカウントを別に作るのは、「1 人または 1 法人が持てる無料のアカウントは 1 つまで」「1 つのログインを複数の人で共有しない」に合わない。commit の作成者は書いた個人（`blacksawa` の非公開用アドレス）のままでよい
  - 組織は Free プラン。所有者は「A business or institution」（株式会社studio C）を選び、GitHub Customer Agreement を会社として結んだ（文書「Upgrading to the GitHub Customer Agreement」によると、標準の利用規約は個人との契約、Customer Agreement は団体としての契約）
  - ドメイン studioc.co.jp を認証済み（Cloudflare の DNS に TXT レコード `_gh-studioc-co-jp-o` を追加。組織の API で `is_verified: true`）。印が付いた後は TXT レコードを消してよい（文書「Verifying or approving a domain for your organization」）
  - `blacksawa/claude-usage-display` から Transfer ownership で移した。古い URL からは自動で転送されるが、古い場所に同じ名前のリポジトリを作ると転送は消える（文書「Transferring a repository」）。記事には組織側の URL を載せる
  - 組織名の `studioc` と `studio-c` は、無関係の第三者が使っている（2017 年作成の個人アカウントと、ラスベガスの組織「Studio C」）
- ライセンスは **MIT**、著作権者は **株式会社studio C**（2026-10-05 ユーザーが決定。`LICENSE` の本文は GitHub の Licenses API の `mit` から作成）
- 履歴にトークンや API の生の応答が入っていないこと（2026-10-05 の初回 commit の前に、トークンらしき文字列・個人のパス・fixture の項目を検査済み）
- 公開範囲の変更は `GH_TOKEN=$(security find-generic-password -s gh-token-studioc-co-jp -w) gh repo edit studioc-co-jp/claude-usage-display --visibility public --accept-visibility-change-consequences` で行う（§3 の組織用のトークン）。GitHub の画面から変えてもよい
- フォント: 画面は macOS に入っているフォント（SF Pro Rounded・ヒラギノ角ゴシック）で描く。リポジトリにはフォントのファイルを含めず、`/System/Library/Fonts/` のパスで参照するだけである。macOS の使用許諾契約（この Mac の `/Library/Documentation/License.lpdf`、日本語版 2 条 E「フォント」）は「Apple ソフトウェアの実行中にコンテンツを表示およびプリントするために、Apple ソフトウェアに含まれるフォントを使用することができます」「当該フォントに付属する埋め込み制限で許可されている場合のみ、コンテンツ内にフォントを埋め込むことができます」と定める。このプログラムは、macOS 上で実行中にこれらのフォントで画面を描き、ディスプレイに表示する。README・記事に載せる画像は描いた結果の画素で、フォントのデータは含まない
