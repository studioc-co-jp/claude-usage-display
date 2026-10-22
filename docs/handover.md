# 引き継ぎ: claude-usage-display（2026-10-05 作成）

`~/projects/studioc` で起動したセッションが、ここまで作った。以降は、このディレクトリで起動したセッションが引き継ぐ。
**このファイルを最初に読み、「残っている作業」を上から順に片付ける。**
記事の素材（これまでに行ったこと・調べたことを、記事に書く話の側から整理したもの）は `docs/article-material.md` にある。

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

2026-10-05 夕方、このディレクトリで起動したセッションが §5 の 1〜5 を終えた時点の状態。2026-10-09 にディスプレイが届き、§5-6 の 1〜6 と 8 を終え、7 の登録まで済ませた（§4-7・§4-8）。

- **GitHub `studioc-co-jp/claude-usage-display` の `main` に push 済み。2026-10-09 に public にした（§5-8）。**2026-10-05 に作成者のメールアドレスを非公開用に書き換えるため、GitHub 上のリポジトリを作り直して push し直し、そのあと会社の組織 `studioc-co-jp` へ移した（§6）
- **自動起動は登録済み**（2026-10-09 08:22 に既定のオプションで登録し直し、ログに「ディスプレイに接続しました」が出た。§5-6 の 7）。ディスプレイをつなぐ前に一度解除していた（§5-6 の 1）。2026-10-05 に登録したとき（既定のオプション。`~/Library/LaunchAgents/jp.co.studioc.claude-usage-display.plist`、ログは `~/Library/Logs/claude-usage-display.log`）に確かめたことは次のとおり
  - 登録・オプションを変えての登録し直し・誤ったオプションの拒否・解除・強制終了後の起動し直し（約 3 秒）を実際に動かして確かめた
  - launchd から起動しても Keychain の読み取りと利用枠の取得が通ることを、`preview` を 1 回だけ動かす使い捨てのジョブで確かめた（§4-6）
- **5.2 インチは 2026-10-15 に届き、利用枠を出している**（`scripts/install-launch-agent.sh --device 5.2 --brightness 40 --icons …`。§4-11・§4-10 の「見出しのアイコン」）。3.5 インチはサーバーの状態の画面（§5-10）
- テストは 125 件すべて成功（2026-10-15 時点）（`.venv/bin/python -m unittest discover -s tests`）。5.2 インチの送信部（`turzx_usb.py`）を足した後、自動起動を起動し直し、3.5 インチで 12:00・12:01 の描き直しがエラーなく送られたことをログで確かめた
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
- **別の Mac（MacBook）で使う場合**（2026-10-09 にユーザーが質問）: プログラムとログは、ディスプレイをつないだ Mac の上にある。ディスプレイには何も残らない。MacBook では README の「別の Mac（MacBook など）で使う」の手順（clone・venv・Claude Code のログイン・自動起動の登録）を行い、ログは MacBook の `~/Library/Logs/claude-usage-display.log` で見る。ディスプレイがつながっていない Mac は API を呼ばない（10 秒ごとに接続を確かめるだけ）
- **利用枠の API の 429（取得の間隔を空けています）**: 2026-10-09 22:15:03（22:18:28 に戻る）と 22:56:29（22:59:57 に戻る）に出た。このツールの間隔は 120 秒のままで、同じ API を同じトークンで呼ぶ Orca（`/Applications/Orca.app`、10 月 7 日から起動中。`app.asar` の中で `https://api.anthropic.com/api/oauth/usage` を呼ぶことを確認）が動いていた。VS Code は起動しておらず、Claude Usage Meter は呼んでいない。どちらが上限に触れたかは、このときのログに Retry-After を残していなかったため分からない。ユーザーの指示で、429 は毎回「Retry-After の値・秒数・名前に ratelimit を含む応答の見出し・次の取得の時刻」を、戻ったときは止まっていた長さを、ログに残すようにした（2026-10-09 23 時台）。Orca が呼ぶ頻度は、`app.asar` の API の呼び出しの前後からは見つからなかった

### ファイル

| パス | 役割 |
|---|---|
| `claude_usage_display/usage.py` | Keychain からトークンを読み、利用枠 API を呼び、`limits` 配列から 3 本を取り出す |
| `claude_usage_display/gauge.py` | 既定の画面（ゲージ型）を描く。480×320 の寸法を `Layout` が高さの比で拡大し、1280×720（5.2 インチ、2.25 倍）でも描く |
| `claude_usage_display/render.py` | 横棒の画面（`--theme classic`）と、画面に共通の部品（フォント、リセット時刻の書式）。確認画面（`render_test_pattern`）もここにある |
| `claude_usage_display/turing.py` | rev A のコマンド組み立て、RGB565（リトルエンディアン）への変換、libusb での送信 |
| `claude_usage_display/server_monitor.py` | サーバーの状態の画面（`monitor`）の取得と判定。設定（`monitor.toml`、git に入れない）を読み、CloudWatch の `GetMetricStatistics` と S3 の監視の状態ファイルを、Keychain の読み取り専用の鍵で読む。赤にするか（`alerts`）・見出しにオレンジで出すか（`warnings`）を決める |
| `claude_usage_display/monitor_screen.py` | サーバーの状態の画面を描く（横置き 480×320・縦置き 320×480 の 2×2。配置は `LANDSCAPE`・`PORTRAIT`。異常のときは画面全体を明るい赤） |
| `claude_usage_display/turzx_usb.py` | 5.2 インチ（TURZX の新しい世代、`1cbe:0050`）への送信。暗号化した 512 バイトの見出し（DES-CBC、鍵 `slv3tuzx`）と PNG（1 MiB を超えると JPEG）を 1 回で書き、応答を確かめる。横向きの画像を縦長に回して送る。PNG は RGBA。2026-10-15 に実機で確かめた（§4-11） |
| `claude_usage_display/__main__.py` | `preview` / `probe` / `test-pattern` / `run` の 4 コマンド。`run` は常駐ループ |
| `tests/` | 単体テスト 97 件。`fixtures/usage_response.json` は実際の応答から必要な項目だけを残したもの |
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
- **`resets_at` は、同じ時刻のリセットでも取得のたびに 1 秒未満前後する。**2026-10-15 に 3 回取ると、週次（`weekly_all`）は 01:00:00.38・01:00:00.22・01:00:00.02（UTC）、Fable 週次（`weekly_scoped`）は 3 回とも 01:00:00 ちょうどだった。2026-10-05 の取得（fixtures）では週次が 00:59:59.96。週次の秒の端数は、同じ応答の 5 時間の枠（09:40:00.38 など）とほぼ同じで、取得した時刻の端数に合わせて動いていた。分を切り捨てて表示していたため、同じ 10:00 のリセットが週次だけ 9:59 と出た（5.2 インチを見たユーザーの指摘）。表示は最も近い分に丸める（`render.nearest_minute`。ゲージ型・横棒の画面とも。「あと…」も丸めた時刻から数える）
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
- 2026-10-09、実機を見たユーザーの指示で文字の色を変えた（§4-8）。右上の更新時刻と「あと…」は Gray → 白（Label）、「リセット」は Gray (2) → Gray。Gray (2) は使わなくなった。13 ピクセル以下になりうる文字は W4 で書く（§4-8）

### 4-6. launchd で分かったこと（2026-10-05、macOS 27.0.1）

- launchd は `LANG`・`LC_ALL` を渡さない。Python 3.14 は C ロケールで UTF-8 モードに自動で入る（launchd 経由で `sys.flags.utf8_mode = 1`、`sys.stderr.encoding = utf-8` を確認）。plist では `PYTHONUTF8=1` を明示している
- launchd から `security find-generic-password` で Keychain を読んでも確認画面は出ず、利用枠の取得まで通った（使い捨てのジョブで `preview` を動かし、終了コード 0）
- **`launchctl bootout` はサービスの終了を待たずに戻る。**直後の `launchctl print` ではまだ読み込まれており、プロセスも残っていた。登録・解除のスクリプトは、`launchctl print` が失敗する（消える）まで待つ
- `KeepAlive` が true なので、`kill -9` で落としても約 3 秒で起動し直した
- macOS 27 の `system_profiler` には `SPUSBDataType` が無く、`SPUSBHostDataType` を使う（`system_profiler -listDataTypes` で確認）

### 4-7. 実機: 電源と USB の認識（2026-10-09、Mac mini M4・Mac16,10、macOS 27.0.1）

ディスプレイが届いた。つないだ時点では自動起動が登録されたままだったが、ログでは接続待ちのままで、ディスプレイには何も送っていない。認識を待つ前に自動起動を解除した（§5-6 の 1）。

| つなぎ方 | ケーブル | 電源 | USB の認識 |
|---|---|---|---|
| USB ハブの USB-A 端子 | 付属の USB-A⇔USB-C（ディスプレイ側に L 字アダプターを挟んでいた。下記） | 入る。画面に「PLEASE RUN THE APP」 | されない。`ioreg -p IOUSB`・`system_profiler SPUSBHostDataType` に `1a86` の機器が無く、`/dev/cu.usbmodem…` も無い。06:53〜07:03 に 0.5 秒ごとに USB の機器の出入りを記録し、出入りは 0 件 |
| Mac mini 本体の USB-C 端子（本体に USB-A 端子は無い） | 別の USB-C⇔USB-C（08:39〜08:40 に L 字アダプターなし・ディスプレイ側のプラグを上下両方の向きで再試験） | 入らない | されない |
| （比較）本体の USB-C 端子に iPhone | 上と同じ USB-C⇔USB-C（08:58） | — | される。`iPhone@02210000`、10 Gb/s |

- **電源の違いは USB Type-C の仕様どおり**（USB Type-C Cable and Connector Specification Release 2.0、USB-IF、2019-08。https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf ）
  - §4.4.2（PDF 141 ページ）: USB-C の端子の電源側は、受電側がつながるまで VBUS を出さない。USB-A などの従来の端子の機器は、この要件から除かれる（つないだだけで 5V を出す）
  - §4.5.1.3.1（PDF 154 ページ）: 電源側は CC 端子の Rd（プルダウン抵抗）で受電側を検出し、検出してから VBUS を出す
  - したがって、本体の USB-C 端子で電源が入らないのは、ディスプレイ側の USB-C 端子が Rd を示していないか、USB-C⇔USB-C ケーブルの CC の線が通っていないか、のどちらか。USB-A の端子からは CC の判定なしに 5V が来るので点く。2026-10-09 08:39:29〜08:40:26 に、L 字アダプターなしでディスプレイ側のプラグを上下両方の向きで試しても、電源は入らず（ユーザーが目視）、USB の機器としても現れなかった（`ioreg -p IOUSB` の 0.5 秒ごとの記録）。**アダプターは原因ではない。**そのうえで、**原因はディスプレイ側の USB-C 端子が Rd を示していないことと確定した**（§5-6 の 8）。2026-10-09 08:58:49 に、同じ USB-C⇔USB-C ケーブルで iPhone（ロック解除済み）を本体の USB-C 端子につなぐと、USB の機器として認識された。経路は `AppleT8132USBXHCI@02000000`（本体内蔵のコントローラー）→ `USB3 Gen2 Hub@02200000`（ベンダー ID `0x05ac`、端子 2 つ）→ `iPhone@02210000`、Link Speed 10 Gb/s（`ioreg -p IOUSB`・`system_profiler SPUSBHostDataType`）。USB-C 同士では、電源側が CC の線で Rd を検出しないと VBUS が出ず、通信も始まらないので、認識されたことはケーブルの CC の線と本体の端子が正常であることを示す。アダプター・ケーブル・本体の端子がどれも正常なので、残るのはディスプレイ側だけである。このケーブルは USB 3 の信号線も通る（10 Gb/s で接続した）
- **対処の候補**: Mac 本体の USB-C 端子に「USB-C（オス）→ USB-A（メス）」の変換アダプターを付け、付属の USB-A⇔USB-C ケーブルでつなぐ。仕様 §3.6.1 の表 3-19 の注 1（PDF 86 ページ）で、この変換アダプターは CC を Rd（5.1kΩ）で GND につなぐと定められているので、Mac は受電側を検出して 5V を出す
- **ディスプレイが要求する電流と速度**（2026-10-09 09:00 ごろ、Mac mini で読んだ）: 構成記述子の `bMaxPower` は 250（500 mA）、`bmAttributes` は `0xa0`（バスパワー）、`bcdUSB` は 2.00（pyusb で読んだ）。macOS の割り当ては `UsbPowerSinkAllocation = 500`（`ioreg -p IOUSB -r -n UsbMonitor -l`）。速度は Full Speed（12 Mb/s）。いまつないでいるハブは 2 段とも Genesys Logic `05e3:0610` で、どちらもセルフパワー（`bmAttributes` `0xe0`）
  - USB 2.0 仕様 §7.2.1（USB-IF の配布物 `usb_20_20250603.zip` の `usb_20.pdf`、PDF 199 ページ・印刷上 171 ページ。https://www.usb.org/document-library/usb-20-specification ）: 1 unit load は 100 mA。バスパワーのハブの外部端子は、1 端子 1 unit load（100 mA）までしか出せない。外部から電源を取るハブは、1 端子 5 unit load（500 mA）を出さなければならない。高電力（5 unit load まで）を使わせる前に電力が足りることを確かめるのは、ソフトウェアの責任
  - したがって、ハブを選ぶ条件は 3 つ: (1) USB-A 端子があること。ディスプレイは Rd を示さないので、ハブの下流の USB-C 端子でも電源は入らない（ハブの下流の端子も電源側で、Type-C 仕様 §4.4.2 が当たる）(2) AC アダプターなどで外部から電源を取る（セルフパワーの）ハブであること (3) 速度は USB 2.0 で足りる。外部モニターの USB-A 端子（モニターの電源で動くハブ）も (2) を満たす
- **認識されなかった原因は、ディスプレイの USB-C 端子に挟んでいた L 字アダプターだった**（2026-10-09 07:10〜07:54、`ioreg -p IOUSB` を 0.5 秒ごとに取って機器の出入りを時刻つきで記録し、ユーザーの付け替えと突き合わせた）
  - アダプター: サンワサプライ `AD-USB38CCFL`（USB-C オス⇔USB-C メス、L 字。最大 40Gbps・240W・DisplayPort Alt Mode をうたう。https://www.sanwa.co.jp/product/syohin?code=AD-USB38CCFL 。USB 2.0 の配線の記載は無い）
  - **アダプターのメス側に挿すケーブルの向きで、USB 2.0 の信号が通るかが決まる。**片方の向きでは、iPhone（付属ケーブル）もディスプレイ（付属ケーブル・手持ちの USB-A⇔USB-C ケーブル）も認識されず、ケーブルを裏返すと認識される。アダプターをディスプレイに挿す向きは結果に関係しない
  - アダプターを外すと、付属ケーブルはディスプレイにどちらの向きで挿しても認識される。手持ちのケーブルも認識される。ハブの端子（Location ID `0x00111000`）・ケーブル 2 本・ディスプレイはどれも正常
  - USB Type-C 仕様 §3.2.3 表 3-4 の注 1（PDF 68 ページ）: メス側は D+/D- を 2 つの位置（Dp1/Dn1・Dp2/Dn2）のどちらでも受けなければならない。ケーブルのプラグは片側の 1 組しか持たない。このアダプターのメス側はこれを満たしていない。§3.6（PDF 85 ページ）は「Only the adapter assemblies defined in this specification are allowed」とし、定めているのはUSB-C → Standard-A メス・USB-C → Micro-B メスの 2 種類だけで、USB-C のオス⇔メスの延長アダプターは定めていない
  - アダプターを使うなら、通る向きでケーブルを挿す（プラグに上下の印を付ける）
  - 切り分けで分かった注意: iPhone は Wi-Fi 経由でも Mac に見える（`usbmuxd` のログの `[com.apple.usbmux:bonjour]`）ので、USB で認識されたかは `ioreg -p IOUSB` で見る。ロック中の iPhone はコンピュータと通信しない（Apple サポート https://support.apple.com/en-us/111806 ）ので、ロックを解除してから挿す
  - zsh では `log` が組み込みコマンドと重なるので、システムログは `/usr/bin/log show` で読む

### 4-8. 実機: 確保・向き・色・転送時間・文字（2026-10-09）

- `probe`: `1a86:5722`、製造元 `Turing`、製品名 `UsbMonitor`、シリアル `USB35INCHIPSV2`（rev A）、Full Speed（12 Mb/s）。interface 0 は class 0x02（0x81 IN、割り込み、8 バイト）、interface 1 は class 0x0a（0x82 IN・0x03 OUT、バルク、64 バイト）。「インターフェースを確保できました」。macOS は `/dev/cu.usbmodemUSB35INCHIPSV21` も作るが、このプログラムは使わない
- `test-pattern`: `--flip` なしで向きが正しく、赤と青の入れ替わりも無い
- 1 画面（307,200 バイト）の転送: 5 回で 1867〜1884 ミリ秒。区切りを 1024・4096・16384・65536 バイトに変えても1865〜1873 ミリ秒で変わらないので、ディスプレイ側の受け取りの速さ（約 164 KB/秒）で決まる。120 秒ごとの描き直しには支障が無い
- `run`: 接続して実際の利用枠を表示した。保存した画像と、ユーザーが撮った実機の写真の配置・色は同じ
- 抜いたとき: 常駐表示は次に画面を送るとき（今回は抜いて 31 秒後）に ENODEV の `USBError` で気づき、接続待ちに戻る。以前は毎回 30 行ほどのトレースバックをログに残していたので、ENODEV のときは「ディスプレイが外れました。接続を待ちます」の 1 行にした（`turing.is_disconnected`。ほかの送信の失敗はトレースバックを残す）
- 文字の調整（ユーザーの指示。実機の写真つき）
  - 「右上の更新時刻と、各カードの一番下の『あと…』が薄くて見えないので、リセット日時と同じ色に」→ 白（Label）
  - 「『リセット』はそこまで見やすくする必要はないが、全く見えないのでもう少し明るく」→ Gray (2)（99）から Gray（142）
- **ヒラギノ角ゴシック W3 は 12・13 ピクセルで「4」の横棒が消える**（実機の写真の「あと3時間40分」でも崩れていた。Pillow 12.3.0・FreeType 2.14.3）。4 倍で描いて縮めると崩れないので、ヒンティングが原因。W3 の 9〜11・14〜16 ピクセルと、W4 の 10〜13 ピクセルは崩れない。縮めて描くと文字がかすれる（§4-5）ので採らず、13 ピクセル以下になりうる文字（「あと…」、更新時刻、取得失敗の文言。横棒の画面の取得失敗の文言も）を W4 にした（`render.SMALL_WEIGHT`）
  - テスト `test_small_weight_keeps_crossbar_of_four`: 「4」の各行で濃い画素が続く幅の最大が、字幅の 0.7 以上。崩れた W3 は 0.33〜0.44、崩れていない字は 0.86 以上。W3 に戻すと 12・13 ピクセルで失敗する

### 4-9. 5 インチへの買い替え（2026-10-09 調査）

ユーザーが「3.5 インチは思っていたより画面が小さい」として、5 インチの購入を決めた（2026-10-09）。5 インチには通信方式の違う 2 種類がある。以下は turing-smart-screen-python（commit `2b33ab4f`、2026-09-04。行番号はこの版）を仕様として読んだもので、コードは流用しない

- 見分け方（wiki「Hardware revisions」 https://github.com/mathoudebine/turing-smart-screen-python/wiki/Hardware-revisions ）: Turing 5" は SD カードの差し込み口があり、USB-C は 1〜2 個。UsbPCMonitor 5" は側面に USB-C が 2 個で、SD カードの差し込み口が無い
- 通信方式（`configure.py` 101〜105・134・141 行目）: Turing 5" は rev C、UsbPCMonitor 5" は rev A
- rev C（`library/lcd/lcd_comm_rev_c.py`）
  - 解像度は 800×480（本来の向きは 480×800。129・237〜238 行目）
  - つないだ直後は休止した状態（シリアル `USB7INCH`、または `1a86:ca21`）。シリアルポートを開く（115200 bps、RTS/CTS）と起き、別の ID（`1d6b:0121`・`1d6b:0106`・`0525:a4a7`、またはシリアル `20080411`）でつながり直す（140〜181 行目）
  - HELLO（`01 ef 69 00 00 00 01 00 00 00 c5 d3`）を送り、23 バイトの応答を読む（43〜48・67 行目）。送るデータは 250 バイトの倍数に詰める（200〜201 行目）
  - 5 インチの画面全体の画像の命令は `c8 ef 69 00 17 70`（87 行目）。画素は BGRA または BGR（35 行目）
- rev A の 5 インチ（UsbPCMonitor 5"）: HELLO（6 バイト）の応答で 3.5・5・7 インチを見分け、5 インチは 480×800（`lcd_comm_rev_a.py` 95〜120 行目）。いまの `turing.py` は応答を読まない
- そのまま使えるもの: `usage.py`（Keychain と利用枠の取得）、`launchd/`・`scripts/`。作り直すもの: 通信部（rev C なら新しく書く）と、画面の配置（480×320 前提の画素の値を 800×480 に。5 インチ・800×480 は計算で約 187 ppi）
- macOS では、rev A はシリアル経由だと画面が崩れたので libusb でじかに書いている（§4-3）。rev C は起こすのにシリアルポートを開くので、macOS でどう送れるかは実機で確かめる
- **購入候補の商品（2026-10-09 調査）**: AliExpress の商品 ID 1005011742654881（「5インチ IPS Type-C モニター 800x480 ブラック」。ユーザーが共有した短縮リンク `https://a.aliexpress.com/_c34x7IpT` の行き先）。ページは JavaScript で描くため、HTML から取れたのは商品名と商品画像 6 枚だけ（仕様の表とストア名は取れなかった）
  - 商品画像の内容: 画面に TURZX の表示、側面に「Type-C port」と「TF card slot」、背面に「TURING SMART SCREEN」のラベル、800×480、122×78×10 mm、アルミの筐体、SD カードの動画・写真を PC なしで再生、付属品に「5Pin to USB-C」「9Pin Cable」「USB cable」（マザーボードの USB 端子につなぐもの）と卓上・ファンのブラケット
  - ユーザーがアプリで開いた商品ページの画面（2026-10-09 11:02〜11:03 のスクリーンショット）: 商品名は「TURZX 5インチ IPS Type-C サブディスプレイ コンピューター LCD ディスプレイ USB ダイナミック ミニモニター 800x480 AIDA64非対応 Windows 10/11用」。説明の「Interface introduction」は「Type-C port ×1、SD card slot ×1、PH port ×1（PH port: hidden interface on the back）」、TF カードは 256 GB まで。「Dynamic background: Support setting dynamic video as theme background」。明細はバッテリー付属 no・主な用途 その他の分野・懸念される化学物質 なし
  - **wiki「Hardware revisions」の Turing Smart Screen 5" に当たる**（SD カードの差し込み口、USB-C が 1〜2 個、マザーボード用の MX-1.25 のコネクター、黒と白、公式ソフトは Windows 用の `UsbMonitorL.exe`）。UsbPCMonitor 5"（rev A）は USB-C が 2 個で SD カードの差し込み口が無いので違う。したがって **rev C**
- **rev C の 5 インチの通信（issue #1030・#1075 とそのコメント。どちらも Linux）**
  - USB には 2 つの姿で現れる。休止中は CH552T のブリッジ（`1a86:ca21`・シリアル `CT21INCH`、または `1a86:ca50`・`CT50INCH`、製品名 `UsbMonitor`）。起こすと別の機種（`1d6b:0106`、ときに `0525:a4a7`、製品名 `Android`、シリアル `20080411`）として現れ、通信はこちらのバルク OUT `0x01`・IN `0x81` で行う（#1030 の Windows の通信の記録）
  - HELLO の応答は `chs_5inch.dev1_rom1.88` または `.89`。画面全体は 800×480 の BGRA（1 画面 1,536,000 バイト）で、命令 `c8 ef 69 00 17 70` と大きさ `0x0E10` の後に、249 バイトごとに `0x00` を挟んで送る（`lcd_comm_rev_c.py` 87・352〜363・393〜395 行目、#1075 のコメント）。送り終えて 1〜3 秒後に `full_png_sucess` が返る
  - 画素を途中で途切れさせると、USB をつなぎ直すまで HELLO も通らなくなる（#1075・#1030 のコメント、Goliohs、2026-09-24）
  - Linux では、シリアル（`cdc_acm`）経由だと約 250 バイトの 1 回で詰まり、libusb で同じ端点に直接書くと動いた、という報告がある（#1075、1 台で検証、open）。同じ機種がシリアル経由でも動いたという反論もある（同 issue の Goliohs のコメント。紹介された実装のリポジトリ `Goliohs/turzx-native-monitor` は 2026-10-09 に GitHub が 404 を返した）
  - 明るさは `SET_BRIGHTNESS`（`0x7b`）、向きはソフトで画像を回す。画面の一部だけを書き換える `UPDATE_BITMAP` もある（`lcd_comm_rev_c.py`）。ライブラリの `auto_detect_com_port` が起こす対象に挙げるシリアルは `USB7INCH`・`CT21INCH`・`CT88INCH` と `1a86:ca21` で、`CT50INCH`（`ca50`）は含まない（142・144 行目）
- **macOS で rev C を動かした報告は見つからなかった**（2026-10-09。issue #7 の全 46 コメントは 3.5 インチ rev A の話だけ。題名に mac を含む issue 3 件（#7・#516・#776）も rev C に触れていない。`USB7INCH`・`ca21`・`rev C`・`5 inch`・`5inch`・`5"` で issue を検索した結果も、macOS の報告は無し）。届いたら、(1) ブリッジのシリアルポートを開いて起こせるか (2) 起きた機種のインターフェースを libusb で確保できるか (3) 全画面を送って `full_png_sucess` が返るか、の順に確かめる
- **ライブラリの外も調べた結果（2026-10-09）**: ウェブ検索と、GitHub のコード検索（`chs_5inch` を含むリポジトリ約 20 件）でも、macOS で rev C を動かした例は見つからなかった。プロトコルの文書を持つ `alexwbaule/turing-screen`（Go、README は「Linux Driver」）と `slipalison/bezel`（Rust、GPL-3.0、Linux と Windows。rev C は「serial + wake MCU」で、実機で確かめたのは 8.8 インチ）は、どちらも macOS に対応していない。ライブラリのリリースノートで macOS に触れた 3.9.2（2025-04-01）は issue #7（3.5 インチ rev A）の修正で、3.10.0（2026-04-12）の「USB で通信し libusb を使う新しい機種」は 5.2 インチ（1280×720）などの新しい世代の話で、800×480 の 5 インチ（rev C、3.0.0 から対応）ではない
- **rev A の 5 インチの購入先**: ライブラリの README が UsbPCMonitor 3.5"/5" として紹介する AliExpress の商品 1005003931363455 は、2026-10-09 の時点で商品名が「3.5 インチ」だが、商品画像に 5 インチの品（800×480、77×121 mm、USB-TYPEC、金属、黒と白。側面に USB-C が 2 つで SD カードの差し込み口なし）が載っている。選べる種類（SKU）はページの HTML からは取れなかった
- **TURZX 公式サイトの製品一覧（2026-10-09 に https://www.turzx.com/en/ で確認）**: 4.6"（960×320）・5.2"（1280×720、127×71 mm、USB-C と PH 1.25、デスクトップモード ✓）・12.3"・9.2"・8.8"・8"・3.5"・2.1" の 8 機種。**対応 OS はすべて Windows**（3.5" は Windows 7-11、ほかは Windows 10, 11）。5"（800×480、rev C）は一覧に無い。5.2" の詳細ページに仕様の文章は無く、購入先は Taobao と JD の公式店
- **5.2 インチ（新しい世代）**: ライブラリ 3.10.0（2026-04-12）が対応した「シリアルではなく USB で通信する」世代で、5.2" は作者が実機で試したとある（リリースノート）。`lcd_comm_turing_usb.py`: VID `0x1cbe`、5.2" は PID `0x0050`（720×1280）。命令は 512 バイトの見出し（先頭 504 バイトを DES-CBC、鍵と IV は `slv3tuzx`）で、画像は PNG（1 MB を超えると JPEG）を 1 枚ずつ送る（JPEG 101・PNG 102、明るさは 14）。ドライバーを外す処理は Linux のときだけ（490 行目）。同じ方式の 9.2"（`1CBE:0092`）を、元の記事の Token Dashboard（MIT）は Windows で WinUSB、ほかでは libusb のバルク転送（IN・OUT 各 1 本）で扱う（`docs/turzx-architecture.md`）。WinUSB を使う＝ベンダー独自のインターフェースなので、macOS はドライバーを当てず libusb で確保できる種類。1 枚ごとに完結した画像を送るので、rev A のような画素の数え違いは起きない。**macOS での報告は見つからなかった**（issue #727・#1007・#1008 は Linux。phstudy/turing-smart-screen-cli（MIT）は README に macOS の手順があるが対象は 8.8"）。#727 には、8.8" V1.1 で `1cbe` ではなく `1a86:ca88`・`0525:a4a7` で現れる個体の報告があり、同じ機種名でも中身の世代が違う個体がある。AliExpress には TURZX 5.2" の出品が 10 件以上ある（例: 1005009897099893・1005010058380485。ユーザーが見た出品は 5,474 円・252 点販売・評価 4.6）。商品説明の「デスクトップモード（拡張画面）」は Windows のドライバーによるもので、Mac では使えない
- **ユーザーが見つけた 5.2 インチの出品（2026-10-09）**: AliExpress 1005010058380485（短縮リンク `https://a.aliexpress.com/_c4lVHa5L`）。商品名「TURZX 5.2インチセカンダリースクリーン 1280x720 USB-C拡張スクリーン … Windows 10/11対応」、画像に「USB 5.2-INCH Secondary Screen」「Resolution 1280x720」「Support Extended Screen」「NO HDMI」。公式の 5.2" と同じ新しい世代
  - 新しい世代（`1cbe`）が macOS で画像を表示した報告は、2026-10-09 の時点で見つからなかった。鍵 `slv3tuzx` を含むコードを GitHub で検索した結果、近いものは次のとおり。`RexPhoe/open-turzx`（MIT、TURZX 2.8" `1CBE:0028`）は README に「macOS untested but structurally compatible」。`hieubui2409/pc-screens` は Lian Li 8.8"（`1cbe:a088`）を「bulk vendor-specific, EP 0x01/0x81」と書く（この系統がベンダー独自のインターフェースであることの別の出典）。`suraj-lab/lianli-hydroshift-macos` は macOS で PyUSB を使い、Lian Li の液晶（`1CBE:A034`・`A021`）のインターフェース 0 を確保して、同じ 512 バイトの暗号化した命令を送る（`scripts/lcd-reboot.py`）。ただし送るのは画面の切り替えの命令で、画像の送信ではない
- **5.2 インチ 1005010058380485 の購入条件（2026-10-09 に商品ページで確認）**: 販売者 Elec-Zone Store、6,074 円（クーポンで 5,474 円）、252 点販売、レビュー 56 件（星 5 が 47・星 1 が 4）。保証の表示は「送料無料」「30 日までに届かない場合は返金」「90日以内返品無料」で、詳細は「ご満足いただけませんでしたか？商品到着日から90日以内にご返送ください。各注文の最初の返品送料は無料です（月に最大5回）」。Mac で動かなかった場合は、到着から 90 日以内に返品できる
- **TURZX 以外の 5 インチ前後（2026-10-09 に AliExpress を検索）**
  - WeAct Studio の表示機は 3.5"（320×480）と 0.96"（80×160）だけ（`WeActStudio.SystemMonitor` の README）
  - ブランドの無い「5 インチ IPS Type-C セカンダリスクリーン 800x480 AIDA64非対応」の出品が多数ある（例: 1005006664141782・1005012568167019・1005011900698264）。TURZX と同じ種類の表示機だが、rev A か rev C かは出品からは決められない
  - 「USB ケーブル 1 本・1024x600・デスクトップ拡張」の出品（1005010120850264・1005008288478787）は、モニターとして映すタイプで、説明は「Windows 10/11用」。Mac の記載は無く、映像の方式も書かれていない
  - HDMI で映す 5 インチ（LESOWN の 800×480 など）は、macOS がモニターとして認識する種類だが、デスクトップの一部になる
  - Waveshare 5inch USB Monitor（1005011785357476）は、ライブラリが「ファームウェアを変えないと使えない」とする機種
  - BeadaPanel は AliExpress に無い。メーカーの販売サイト（NXElec store、cjcsh.com）の一覧ページの価格は 5C が $30.00、5S が $73.00（ほかに 2・2W・3・4・6・6P・7・8）。日本への発送と返品の条件は、一覧ページに記載が無かった
- **NXElec BeadaPanel 5 / 5C / 5S**（800×480 または 854×480）: メーカーが通信の仕様書（Panel-Link v1.0・Status-Link v1.1）を公開。USB の ID は `4E58:1001`（手引きのレジストリのキー）、ベンダー独自のバルク端点で PNG・JPEG を送り、`SET_BACKLIGHT` で明るさを変える。メーカーのウェブ版ツール（www.nxelec.com/service/beadatools）は WebUSB（`claimInterface`・`transferOut` など）で通信する。製品ページの対応 OS は Linux と Windows。AliExpress の日本語版で「beadapanel」を検索しても出品は無く、購入先はメーカーサイトの Store（cjcsh.com）
- **普通の小型モニター**: AliExpress には HDMI の 5 インチ（800×480、Raspberry Pi 向け）や 5.5 インチのカメラ用モニターがある。macOS がモニターとして認識するが、デスクトップの一部になり（ウィンドウが移る）、映像出力を 1 つ使い、プログラムも「全画面のウィンドウに描く」形に作り替えることになる
- 電源: USB-C⇔USB-C で電源が入るか（ディスプレイ側が Rd を示すか）は、商品画像と issue からは分からなかった。3.5 インチと同じく、USB ハブの USB-A 端子と USB-A⇔USB-C ケーブルなら給電できる（§4-7）

### 4-10. Claude 以外の利用枠（2026-10-11 調査）

5.2 インチに Claude 以外も載せられるかを調べた。

- Claude: 利用枠 API の `limits` は 3 つ（5 時間・週次・Fable 週次）で、画面に出しているものがすべて
- Gemini CLI（公式 `docs/resources/quota-and-pricing.md`）: Google アカウントでは 1 日の回数（無料 1,000・Google AI Pro 1,500・Ultra 2,000）。5 時間の枠は無い
- Antigravity（公式 https://antigravity.google/docs/plans ）: Pro・Ultra は「5 時間ごとに回復」で週の上限もある。量は公表していない
- この Mac で Orca から使っているのは Antigravity（`agy` 1.3.1）。Gemini CLI（`gemini`）は入っていない。Orca 1.4.222 は Gemini と Antigravity を別々に読む（`app.asar` の `out/main/index.js`）
  - Gemini: `~/.gemini/oauth_creds.json` のトークンで内部 API（`cloudcode-pa.googleapis.com/v1internal:loadCodeAssist`・`retrieveUserQuota`）を呼ぶ。トークンの更新に Gemini CLI 本体の OAuth クライアントを使い、更新したトークンをこのファイルに書き戻す
  - Antigravity: `agy -p /usage --output-format json --print-timeout 20s` を実行して結果の JSON を読む。`agy` 1.1.11 以上が条件で、それより古い版は `/usage` をプロンプトとして扱い枠を使ってしまう（Orca は応答の `num_turns` が 1 以上か `conversation_id` があると取得をやめる）
- `agy` 1.3.1 で `/usage` を実行した結果（2026-10-11）: `status` は `SUCCESS`、`num_turns` は 0（枠を使っていない）。`command.data.groups` に「Gemini Models」と「Claude and GPT models」の 2 グループがあり、それぞれに `window` が `5h` と `weekly` の枠（`remaining_fraction`・`reset_time`）がある。`description` の文言は「Within each group, models share a weekly limit and a 5-hour limit. … your weekly limit is tied directly to your individual tier.」
- **5.2 インチに Gemini の枠を足した**（2026-10-11、ユーザーの指示。`antigravity.py`・`gauge.render_with_gemini`、`run`・`preview` の `--gemini`）。画面はユーザーが見本の 2 案から「案 B」（上の段に Claude Code の 3 枚、下の段に Gemini の 2 枚を横長のカードで）を選んだ。見本は `docs/images/gauge-gemini-1280x720.png`
  - **下の段の名前**（2026-10-13、ユーザーが選んだ）: 見出しを「Gemini」から出どころの「Antigravity」に変え、カードを「Gemini 5時間」「Gemini 週次」にした。値は Antigravity の Gemini のモデルのグループの枠で、Gemini アプリや Gemini CLI の枠ではない（Gemini CLI の上限は公式の `quota-and-pricing.md` に 1 日の回数で書かれている）。「Gemini」だけでは、その区別が付かないため
  - **見出しと明るさを 3.5 インチに合わせた**（2026-10-13、ユーザーの指示「Claude Code・Antigravity の表記と更新時刻は、3.5 インチの表記と文字・明るさを合わせて」）。3.5 インチのサーバー監視の画面（縦置き）は名前 15・時刻 16 ピクセルで、どちらも白。5.2 インチの見出しの時刻を、同じ比になるよう 29→36 ピクセルにした（`gauge.GEMINI_STAMP`。名前は 34 ピクセルのまま。`render_with_gemini` だけで、Gemini を出さない画面は変えていない）。文字の色はもともと同じ白なので、「明るさ」は画面の明るさとして、5.2 インチの自動起動も 3.5 インチと同じ `--brightness 25` にした。パネルが違うので、同じ 25% で同じ明るさに見えるかは実機で見比べることにした（5.2 インチの明るさの命令は 0〜102 の値、3.5 インチは 255 − 明るさ × 255 ÷ 100）。**2026-10-15 に見比べ、5.2 インチは 40% にした（§4-11）**。このときの登録は `scripts/install-launch-agent.sh --device 5.2 --gemini --brightness 25`（同日 15:25 に `--gemini` を外した。次の項目）
  - **5.2 インチに Antigravity の枠を出すのはやめた**（2026-10-13 15:25、ユーザーが決定。自動起動の登録から `--gemini` を外し、`scripts/install-launch-agent.sh --device 5.2 --brightness 25` にした。機能とテストは、横棒の画面と同じく戻せるように残す）。理由: Antigravity は rikkama-column の画像生成にしか使っておらず、これまでにかかった上限は画像生成の上限だけ。**`/usage` に画像生成の枠は無い**（グループは「Gemini Models」「Claude and GPT models」の 2 つで、枠は 5 時間と週の 4 つだけ）。rikkama-column の `.agents/AGENTS.md` によると、画像生成の上限は週次で、毎週水曜 16:26:17 JST に補充され、目安は 45〜60 回、超えると 429。2026-10-11 1:54 に `/usage` を読んだとき Gemini の週の枠は 6% だったが、同じ時刻に rikkama-column のセッションは「今週は 41 回、1:53 の実行で 46 回前後になり週の上限の下限に届く」と記録していた。画像生成が上限に近くても `/usage` の Gemini の枠はほとんど動かないので、画面に出しても役に立たない。加えて、15 分ごとの `agy` の起動（約 6 秒）と `implicit/` のファイルの増加が無くなる
  - **5.2 インチの 3 枚の画面のカードの中身を大きくした**（2026-10-13、ユーザーの指示「3.5 インチはサークルなどの表示を大きくした。5 インチでも余白が大きいので同じように表示する情報を大きく」）。`gauge.LARGE`（`layout_for`）で、1280×720 のときだけカードの中身（リング・数字・文字・行の間）を 1.2 倍にした。リングの直径は 225→270 ピクセル。1.3 倍も試したが、中身の高さ 606 に対してカードの高さが 612 で、上下の余白が 3 ピクセルしか残らず、文字がカードの縁に付いた。1.2 倍では上下に 27 ピクセルずつ残る。3.5 インチの大きさ（480×320）の画面は 1 ピクセルも変わっていない（変更前と描き比べた）。見本は `docs/images/gauge-1280x720.png`
  - **「あと…」を「リセット」の見出しと同じ書き方にした**（2026-10-13、ユーザーの指示「あと x 分の表記はリセットと同じように」）。「リセット」には灰色の小さい見出しと白く太い時刻の 2 つがあるので、見本の 2 案を見せ、ユーザーが灰色の見出しのほう（Gray 142・Caption 1・W3）を選んだ。1280×720 のときだけ（`gauge.LARGE` の `quiet_remain`）。3.5 インチの大きさは、2026-10-09 に「薄くて見えない」として白にした経緯があり、12 ピクセルの W3 は「4」の横棒が消えるので、白の W4 のまま（1 ピクセルも変わっていない）。使っていない 2 段の画面も同じ書き方にした
  - **見出しの時刻の大きさを 3 枚の画面にも入れた**（2026-10-13）。3.5 インチに合わせた時刻の大きさ（16 pt 相当、36 ピクセル）を 2 段の画面だけに入れていたため、Antigravity の表示をやめたときに 29 ピクセルに戻っていた。`gauge.LARGE` の `stamp` に移し、1280×720 では 3 枚の画面も 2 段の画面も 36 ピクセルにした
  - **使っていない枠のリセット時刻は出さない**（2026-10-13）。15:19 に `/usage` を読むと、使用 0% の枠の `reset_time` は「取得した時刻＋枠の長さ」だった（5 時間の枠は 20:19、Claude・GPT の週の枠はちょうど 7 日後）。取得のたびに先へずれるので、`remaining_fraction` が 1 の枠はリセット時刻を無し（画面は「--」）にした
  - 内部 API を自分で呼ばず、`agy` の `/usage` を読む。版が 1.1.11 より古ければ呼ばない。応答に `num_turns` が 1 以上か `conversation_id` があれば、起動し直すまで取得をやめる（Orca と同じ止め方）
  - 1 回の実行で `agy` は言語サーバーを起動し、内部 API（`loadCodeAssist`・`fetchAvailableModels`・`retrieveUserQuotaSummary` など）を呼ぶ。約 6 秒かかる（2 回測って 6 秒前後）。キーチェーンの自分のトークンで認証する（このプログラムはトークンを読まない）
  - `--log-file` を付けないと、1 回 21 KB のログが `~/.gemini/antigravity-cli/log/` に増え、`cli.log` の向きがその新しいファイルに変わる（2026-10-11 01:54 の 1 回目で起きた。Orca で動いている agy のログは別のファイルに書き続けていた）。付けると、どちらも起きない。ただし `implicit/` に 450 バイトほどのファイルが毎回 1 つ増える（01:54 と 02:16 の 2 回で 1 つずつ）
  - 実行したフォルダが作業場所になるので、専用の `~/Library/Application Support/claude-usage-display/agy/` で実行し、ログもそこに直近の 1 回分だけ置く。取得は既定で 15 分ごと（`--gemini-interval`、300 秒以上）。launchd は PATH を渡さないので、`agy` は `/opt/homebrew/bin` なども探す（PATH を `/usr/bin:/bin:/usr/sbin:/sbin` に絞って読めることを確かめた）
- **見出しのアイコン**（2026-10-11、ユーザーの指示）: `--icons フォルダ` で `claude.png`・`gemini.png` を見出しの左に出す。Anthropic の Trademark Guidelines（https://www.anthropic.com/legal/trademark-guidelines 、2024-08-01 発効）はロゴの使用に事前の承認を求め、改変を禁じる。Google の商標の指針（https://partnermarketinghub.withgoogle.com/brands/google/trademarks-and-terms/trademark-guidelines-for-proper-usage/ ）は承認された素材だけを使い、製品のアイコンをまねないよう求める。どちらにも個人で使う場合の例外は書かれていない。そこでユーザーが「ロゴは手元だけ」と決めた: 画像は git に入れず、この Mac の `~/Library/Application Support/claude-usage-display/icons/` に置く。README の画像は `--icons` を付けずに作る
  - **アイコンは使わないことにした**（2026-10-11 2:33、ユーザーの指示）。アイコン付きの画面を見たうえで「情報量が多くて見づらくなる」として、自動起動の登録から `--icons` を外した。機能（`--icons`）と、この Mac の画像のフォルダは、戻せるように残している（横棒の画面を残しているのと同じ考え）
  - **5.2 インチの見出しに Claude のマークを出すことにした**（2026-10-15 08:45、ユーザーの指示「5.2 インチの左上に Claude Code のアイコンを付けたい。アイコン＋Claude Code の状態に」）。候補 4 つ（A: Claude.app のアイコン、B: Claude Code の VS Code 拡張機能のアイコン `claude-logo.png`、C: Claude Code のキャラクター `clawd.svg`、D: 拡張機能の `claude-logo.svg` のオレンジのマークだけ）を見出しに入れて実機で順に見せ、ユーザーが D を選んだ。登録は `scripts/install-launch-agent.sh --device 5.2 --brightness 40 --icons "$HOME/Library/Application Support/claude-usage-display/icons"`。Gemini の枠は出していないので、`gemini.png` は使われない。コードは変えていない（2026-10-11 に作った `--icons` のまま。見出しのアイコンは 20 × 2.25 = 45 ピクセル角）
  - **その後、見出しのアイコンを Claude Code のキャラクター（Clawd）に変えた**（2026-10-15 15:11、ユーザーの指示「いまのアイコンとキャラクターのアイコンをもう 1 回比較したい」）。いまのマーク（D）とキャラクター（C）を、5.2 インチに 6 秒ずつ交互に出し（15:10:44 から）、ユーザーがキャラクターを選んだ。45 ピクセルの枠では横 45・縦 35 ピクセルになり、目（約 4 ピクセルの穴）は残る。`claude.png` を差し替え、それまでのマークは `claude-mark.png` に名前を変えて残した。コードは変えていない
  - Gemini アプリ（`/Applications/Gemini.app`、`com.google.GeminiMacOS` 1.128.7.1072、署名の TeamIdentifier `EQHXZ8M8AV`）を入れたあとに調べた結果: `AppIcon.icns` は最大 256×256。`Assets.car` に 1024×1024 のアプリのアイコン（白い角丸の四角に星）と、星の印だけの `AppIcon_Assets/gemini`（1024×1024）がある。`assetutil --info` で一覧を出し、AppKit の `Bundle.image(forResource:)` で PNG に書き出せた。使うことになったら、PDF から切り出した星よりこちらのほうが解像度が高い
  - この Mac の画像の出どころ: `claude.png` は、Claude Code の VS Code 拡張機能の `resources/clawd.svg`（47×38 の枠に `#D97757` の 1 色。目は穴）を、macOS の `NSImage` で 1024×827 の透明の地の PNG に描いたもの（2026-10-15 15:11）。`claude-mark.png`（15:11 まで `claude.png`）は、同じ拡張機能（`~/.vscode/extensions/anthropic.claude-code-2.1.288-darwin-arm64/resources/claude-logo.svg`。SVG の題は「Claude」、色は `#D97757`）を、macOS の `NSImage` で 1024×1024 の透明の地の PNG に描いたもの（2026-10-15）。それまでの `claude.png`（Claude.app のアイコン。`Contents/Resources/electron.icns` を `sips` で PNG にしたもの。1024×1024）は、戻せるよう `claude-app.png` に名前を変えて残した。`gemini.png` は Google Cloud のアイコンのページ（https://cloud.google.com/icons ）の手引きの PDF（`google-cloud-product-icons.pdf`）の 4 ページ目にある Gemini の画像（星の印と「Gemini」の文字の組）から、星の印を切り出したもの（341×340）。配布の ZIP（コアプロダクト・カテゴリ・以前のアイコン）には Gemini の画像は無かった（2026-10-11 に確認）

### 4-11. 実機: 5.2 インチ（2026-10-15、Mac mini M4・Mac16,10、macOS 27.0.1）

2026-10-15 の朝にユーザーがつないだ。§5-9 の手順で確かめた。

- **USB**: `1cbe:0050`、製造元 `TURZX`、製品名 `TURZX1.0`。USB ハブ経由で 480 Mb/s（High Speed）、電源の割り当ては 120 mA。シリアル番号は個体ごとの値なので記録しない。インターフェースは 0 の 1 つだけ（class `0xff`、カーネルのドライバー無し）で、バルクの IN `0x81`・OUT `0x01`（どちらも 512 バイト）。`probe` で「インターフェースを確保できました」。3.5 インチと違い、macOS はシリアルポートを作らない
- **電源を入れただけの画面**: 紫と青の背景の画像に、右上に「TURZX V2」
- **応答**（`test-pattern` の表示。3 つとも `turzx_usb.check_response` の想定どおり「命令番号・`c8`・見出しの時刻 4 バイト」）
  - 命令 10（同期）: 512 バイト。9 バイト目から ASCII で `turzx_0001_0015`（0 でないバイトは 23 バイト目まで）
  - 命令 14（明るさ）・102（PNG）・101（JPEG）: 時刻の後は 0
- **PNG は RGBA で送らないと正しく映らない。**最初に送った RGB の PNG（色の型 2）は、応答は正常なのに、既定の背景が透けたうえで、明るい文字と白の部分だけが縦に 4 回繰り返して描かれた（赤・緑・青の面は出ない）。ライブラリは画面の状態を RGBA の画像として持ち、それを PNG にして送っている（`lcd_comm_turing_usb.py` の `LcdCommTuringUSB.__init__`・`_encode_png`。消去の命令で送る固定の PNG も色の型 6）。同じ確認画面を RGBA（全面不透明）の PNG にして送ると、正しく映った。`encode_image` を RGBA にした
- **画面は 2 つの層でできている。**次の順に送って確かめた
  1. RGBA の PNG（確認画面）→ 正しく映る
  2. JPEG（命令 101。右下に「JPEG」と書いた確認画面）→ 応答は正常だが、画面は変わらない
  3. 全面が透明の RGBA の PNG（720×1280）→ 2 の JPEG の画面が現れる
  JPEG は下の層（既定の背景の画像がある層）に描かれ、PNG は上の層に透明度つきで重なる。1 の不透明の PNG が 2 の JPEG を隠していた。token-dashboard は 9.2 インチで JPEG だけを送っていて（`internal/turzx/protocol.go`）、PNG を送らないので隠れない。このプログラムは PNG で送り、1 MiB を超えて JPEG にしたときだけ、続けて透明の PNG を送る（`TurzxUsb.show`。上の 2→3 の順）
- **向き**: 横置きで、ケーブルを左側に出す置き方のとき、`--flip` 無しで正しい（左上が赤で「左上」）
- **転送時間**（5 回）: 確認画面（RGB の PNG、29,255 バイト）は PNG にする時間を含めて 63〜76 ミリ秒。ゲージ型（見本の値、RGBA の PNG、142,450 バイト）は、PNG にする 20 ミリ秒を含めて 102〜114 ミリ秒。3.5 インチ（約 1.87 秒）の 1/17 ほど
- **常駐**: 自動起動を登録したままつないだ（§5-9 の手順では先に止めることにしていた）。利用枠の常駐は `--device 5.2`、サーバーの状態の常駐は `--device 3.5` なので、同じパネルに 2 つのプロセスが書くことは無い。07:46:29 に「ディスプレイに接続しました」（同期と明るさの応答が想定どおりだった）。このとき送ったのは RGB の PNG で、その画面をユーザーは見ていない
- **`probe` を直した**: 3.5 インチをサーバーの状態の常駐が使っていると、3.5 インチを確保できずに（`USBError(13, 'Access denied (insufficient permissions)')`）その場で終わり、5.2 インチまで確かめなかった。確保できない機器があっても残りを確かめ、最後に終了コード 1 を返すようにした
- **明るさを 40% にした**（ユーザーが実機で決めた）。25%（3.5 インチと同じ値）では「3.5 インチと比べて少し暗い」。上部に「明るさ ○%」と書いた見本の画面で 30・35・40・50% を 6 秒ずつ切り替えて見比べ、ユーザーはいったん 30% を選び、次のリングの地の見比べ（35%）のあとで 35% にした。続けて「あと 5% 明るくしたい」で 40% にした（08:24）。パネルの値は 40 × 102 ÷ 100 = 40（0〜102）
- **色**: ユーザーが「青いリングの色が 3.5 インチよりくすんで見える」と指摘した。調べた結果
  - リングの青い弧（使った分）は同じ色。5.2 インチへ送る PNG は `(0, 145, 255)`、3.5 インチは RGB565（`0x049f`）で `(0, 146, 255)` 相当。見え方の違いはパネルの差
  - リングの地（まだ使っていない分の輪）は、コードの上でも違う。利用枠の画面は青をカードの灰色へ 75% 寄せた `(25, 60, 88)`（`gauge.TRACK_MIX`）、サーバーの状態の画面は青を黒へ 78% 寄せた `(0, 32, 56)`（`monitor_screen.py`）。そのときの 5.2 インチは 2%・13%・0% で、リングのほとんどが地の色だった
  - 地を `(0, 32, 56)` の作り方にした画面と今の画面を、5.2 インチに 5 秒ずつ交互に出して見比べ、**ユーザーは今の地を選んだ**（コードは変えていない）
  - **続けて、弧の青を 5.2 インチだけ `(0, 105, 255)` にした**（08:30 ごろ、ユーザーの指示「3.5 と比べるとリングの現在の値の青がちょっと暗い色に見えるから、もう少し鮮やかな色に」）。3 枚のカードに候補を並べて実機で見比べた。明るい方向（緑を増やした `(0, 165, 255)`・`(0, 185, 255)`）は選ばれず、「いまの色のまま、もう少し濃い色に」で緑を減らした `(0, 125, 255)`・`(0, 105, 255)` を並べ、ユーザーが `(0, 105, 255)` を選んだ。赤 0・青 255 のままなので、彩度は最大のまま。`gauge.LARGE` の `blue` で、3.5 インチ（480×320）の画像は 1 ピクセルも変わっていない（直す前後で 3 種類の画像を比べた）。地は今の `BLUE` から作るので変わらない。3.5 インチのサーバーの状態の画面も `BLUE` のまま
  - **5.2 インチのカードの面をやめ、黒地に縦の区切り線にした**（08:50、ユーザーの指示「3.5 と 5.2 の色が違って見える原因の 1 つが、カードの背景に薄い色が付いていること。カードの面を消して黒背景にし、3.5 と同様に薄く縦に区切り線を」）。`gauge.LARGE` の `cards: False`。区切り線はカードの間の中央に、カードと同じ高さ（CARD_TOP から下の余白まで）で、色は `CARD`（33, 32, 33）、幅は 1 × 2.25 を丸めた 2 ピクセル（サーバーの状態の画面は 1 ピクセル・同じ色）。リングの地は、黒へ寄せる作り（`DARK_TRACK_MIX` 0.22。サーバーの状態の画面と同じ値を定数にした）と、いままでのカードの灰色へ寄せる作りを実機で交互に見せ、ユーザーが前者を選んだ。480×320 の画像・Antigravity を足した画面（カードのまま）・サーバーの状態の画面は 1 ピクセルも変わっていない（直す前後の画像を比べた）。常駐の送り先の向きのテストは、カードの面の色で確かめていたので、左のリングの弧の色で確かめるように直した（逆に回すと落ちることを確かめた）
  - **リングを 1.15 倍にし、「あと…」を日時に寄せた**（09:00 ごろ、ユーザーの指示「カードが無くなった分、下の隙間が気になる」→「リングのサイズを少し大きく。その分リセット以降を下に」→「1.15 倍にしたうえで、あと x 時間の表記を少し上に（リセット時刻との隙間を縮める）」）。リングは 1.00・1.05・1.10・1.15 を、「あと…」の位置は日時との間 27（いま）・22・18 を実機で順に見せ、ユーザーが 1.15 と 22 を選んだ。`gauge.LARGE` の `ring`・`remain_gap`。名前の位置は変えない（`gauge.content_top` が、リング等倍・間 27 のときの中身をカードの高さの中央に置く位置を返す）。結果: リングの直径 270→310 px、日時と「あと…」の隙間 38→24 px（「リセット」と日時の隙間と同じ）、下の余白 54→27 px（左右の余白と同じ。区切り線の下端とも揃う）。名前とリセット時刻は、どちらも Subhead 15 pt × 1.2 × 2.25 = 40 px の W6（ユーザーの質問に答えた）。480×320 の画像・Antigravity を足した画面・サーバーの状態の画面は変わっていない（同じ分に描いて比べた）
  - **両方の画面の、状態ごとの色を実機で見てもらい、すべて今のままにした**（ユーザーの指示「3.5、5.2 ともに全てのアラート状態の色を確認したい」）。見本の値の画面を順に出した（AWS も利用枠の API も呼んでいない）。5.2 インチ: 通常 40%（青）・注意 75%（オレンジ）・危険 95%（赤）／取得の失敗（前回の値のまま、見出しにオレンジの「!」と文言）／値が無い（最初の取得に失敗）。3.5 インチ（左上の名前を状態の名前に差し替え）: 正常／注意（しきい値の 15 ポイント手前からオレンジ）／しきい値超えが 1 回だけ（リングだけ赤）／画面全体が赤（続けて超えた・サイトの異常）／値が届かない（画面全体が赤）／ジョブ障害（見出しにオレンジ）／AWS からの取得失敗（見出しにオレンジ、時刻は「時点」）。監視の停止も画面全体が赤で、同じ色
  - 見比べのスクリプトが 5.2 インチを開いたまま常駐を登録すると、常駐は「ディスプレイを開けません」（`USBError(13, 'Access denied …')`）を 1 回だけ記録し、10 秒ごとに開き直して、スクリプトが終わった後に接続した（08:34:08 → 08:34:28）。背景で起動したスクリプトは SIGINT を受け付けないので、止めるときは SIGTERM を送る
- **Antigravity の枠も実機で一度出した**（ユーザーの指示「取りやめにした Antigravity も表示してみて」）。`--gemini` を付けて登録し直し、08:06:16 に接続、`agy` の取得も失敗なく通った（ログは専用のフォルダの `agy.log` の 1 回分だけ）。実際の値の 2 段の画面を見たうえで、**ユーザーは出さないに戻すと決めた**。08:07 に `--gemini` を外して登録し直した
- 縦置き（`TurzxUsb` の `portrait`）は実機で試していない（この日は横置きだけを確かめた）

### 4-12. 焼き付き対策（消灯）と、確かめる途中の Mac のフリーズ（2026-10-15）

- **きっかけ**: 元の記事の作者（nuits_jp）から、token-dashboard に焼き付き防止を足したので参考に、と返信があった（ユーザーが X のスクリーンショットを共有）
- **token-dashboard の焼き付き対策**（2026-10-12 の PR #42、コミット `8ccc63c`。`docs/usecases/USBディスプレイの焼き付きを防ぐ/`、`internal/display/service.go`・`away.go`、`internal/presence/watch_windows.go`）
  - ずらし: 3 分ごとに、送る画像全体を (0,0)→(4,0)→(4,4)→(0,4)→(-4,4)→(-4,0)→(-4,-4)→(0,-4) の順にずらす。空いた所は画像の左上の角の色で埋める。間隔と量は固定
  - 消灯: 無操作が `Away time`（既定 10 分、1〜240 分。`GetLastInputInfo` を 1 秒ごと）、モニターの電源オフ（`GUID_CONSOLE_DISPLAY_STATE`）、スリープ、ロックなど（`WTSRegisterSessionNotification`）のどれかで、黒の JPEG を送る。消灯中も取得は続ける
- **ずらしは入れない**（ユーザーが決定）。ユーザーの「ずらすのは焼き付き防止に本当になると思う？」に、調べて答えた
  - 液晶の残像は、同じ表示を長く続けると液晶の中にイオンがたまり直流の電圧が残ることで起きる（米国特許 10883049、UCF の論文 https://api.creol.ucf.edu/Publications/9435.pdf ）。一時的で、消せる（Apple https://support.apple.com/en-hk/100952 。対策としてスリープとスクリーンセーバーだけを挙げ、ずらしには触れない）
  - Orient Display（https://www.orientdisplay.com/?p=414321 ）は、静止画を 20 分より長く出さない、動くスクリーンセーバー、表示の定期的な切り替えを挙げるが、ずらしの効き目の説明は無い。NEC の業務用液晶（LCD5710 の説明書）には「画像をゆっくり動かす」機能があるが、量と効果の記述は抜粋に無い。Samsung の Pixel Shift は有機 EL の焼き付きの対策として説明している
  - 4 ピクセルずらして表示が変わるのは、色の境目から 4 ピクセル以内の画素だけ（黒地やリングの内側は変わらない）。画面の端との余白が ±4 ピクセル変わり、2026-10-15 にそろえた余白（左右・下とも 27 ピクセル）が崩れる
  - 3.5 インチは IPS 液晶（CNX Software の 2022-04-29 の記事）。5.2 インチのパネルの種類は、記録した商品情報に無く、商品ページは本文を取得できず確定しなかった
- **消灯の条件**: ユーザーは最初「Mac の画面が消えたとき」を選んだが、確かめる途中で次のことが起き、「無操作 10 分」（`HIDIdleTime`）に変えた（ユーザーが決定）
  - `ioreg -r -c IOMobileFramebufferShim -d 1` の `CurrentPowerState` は、`pmset displaysleepnow` で Mac の画面（3 台）を消しても 1 のままだった（09:14:35〜09:15:01 に 1 秒ごとに記録。ユーザーの同意を得て消した）。Apple シリコンのこの Mac には `IODisplayWrangler` が無い（`pmset -g powerstate IODisplayWrangler` が失敗する）
  - CoreGraphics の `CGDisplayIsAsleep`（SDK の `CGDisplayConfiguration.h` 285〜288 行目「Return true if the display is asleep」）は、ctypes で呼べて 3 台とも false を返した（09:15:58〜59。1 回目 35 ms）
  - **その直後に Mac がフリーズし、ユーザーが再起動した**（起動 09:19:46）。記録（`/Library/Logs/DiagnosticReports/WindowServer-2026-10-15-091656.ips` と `WindowServer_2026-10-15-091720_Mac-mini.userspace_watchdog_timeout.spin`）から分かったこと:
    - WindowServer のメインスレッドが 40 秒応答せず、watchdog が止めた（09:16:16 ごろから。記録の時点で画面の状態は OFF）
    - メインスレッドは TCC の問い合わせ（`com.apple.tcc.preflight.kTCCServiceListenEvent`）で `tccd`（09:16:09 ごろ起動）を待ち、`tccd` は署名の確認で `trustd` を待っていた
    - `trustd` は自分のデータベースのファイルを開く許可を、ESET の Endpoint Security の拡張（`com.eset.endpoint` 10.0.2100.0、「ESET Real-time File System Protection」）に求めて待ち、その ESET は同じ `trustd` を待っていた（互いに待つ行き詰まり）
    - 新しいプロセスの起動（`xpcproxy` 145 件）とファイルを開く処理が EndpointSecurity の順番待ちで止まった。サーバーの状態の常駐の 09:16:22 の「Keychain に鍵がありません」もこの間の失敗
    - 2 つの常駐は待ち状態で、この連鎖に入っていない。`CGDisplayIsAsleep` を問い合わせたスクリプトは、止まった時点では終わっていた。WindowServer の TCC の問い合わせがどのプロセスのためのものかは記録に無く、問い合わせとの関係は確定しなかった
    - ESET の公式情報で、この組み合わせを扱ったものは見つからなかった（ESET の Mac 版でのフリーズの報告は、古い版でフォーラムに複数ある）
  - `HIDIdleTime` は `ioreg -c IOHIDSystem -d 4` で読め、1 回 10 ms ほど。WindowServer にも TCC にも問い合わせない。この Mac は `pmset -g` の `displaysleep 10` なので、10 分で Mac の画面とほぼ同じ時に消える。ずれるのは、Safari などが画面のスリープを止めているとき（USB の 2 台だけが消える）と、ホットコーナーなどで画面をすぐに消したとき（USB の 2 台は 10 分まで点いたまま）
- **作ったもの**（`presence.py`、`turing.py`・`turzx_usb.py` の `blank`・`unblank`、`__main__.py` の `_Resident`、`run`・`monitor` の `--away-minutes`（既定 10、0 で消灯しない））
  - 5 秒ごとに無操作の時間を読む（`POLL_SECONDS`）。読めないときは消灯せずに表示を続け、警告を 1 回だけ記録する
  - 3.5 インチは `SCREEN_OFF`（108）・`SCREEN_ON`（109）（ライブラリの `lcd_comm_rev_a.py` の `ScreenOff`・`ScreenOn` は、この命令を値 0 で送るだけ）。5.2 インチは消す命令が無いので、黒一色の不透明の PNG と明るさ 0。黒の JPEG は前の PNG に隠れる（§4-11）。どちらも実機で真っ暗になり、点け直しも正しく戻ることをユーザーが確かめた（09:33）
  - 利用枠の常駐は、消灯中は取得しない（戻ったときに、止まっていた取得から始める）。サーバーの状態の常駐は取得を続け、画面全体が赤の異常のときは点灯して赤を出す（ユーザーが決定）
  - 消灯までを 1 分にして launchd で動かし、ユーザーが実機で確かめた。ログ: 利用枠 09:53:38 消灯・09:56:01 点灯、サーバーの状態 09:53:40 消灯・09:56:05 点灯。その後、既定の 10 分で登録し直した（09:56:24・09:56:26 に接続）

### 4-13. サーバーの状態の画面の見出しのロゴ（2026-10-15）

- **3.5 インチのサーバーの状態の画面の見出しに、サイトのロゴを出すことにした**（2026-10-15 15:10、ユーザーの指示「5 インチの左上に Claude のアイコンを表示するようにしたけど、3.5 インチの左上に（サイトの）ロゴを表示するようにしたい」）。用意する画像を聞かれ、白一色・背景透明の PNG、一辺 256 ピクセル以上の正方形と答えた（地は普段は黒、異常のときは赤になり、黒や赤のロゴはどちらかで見えなくなるため）。ユーザーが用意した画像は 512×521 の RGBA で、不透明の部分は白（255, 255, 255）だけだった
- `monitor.toml` の `logo` に画像のパスを書く（`~` と、設定ファイルからの相対パスが使える。無ければ設定の誤りとして止める）。画像はアイコンと同じフォルダに置き、リポジトリには入れない。大きさと縦の位置は、利用枠の画面の 3.5 インチのアイコンと同じ（`gauge.ICON_SIZE` の 20 ピクセル角の枠、名前の基準線から 5.5 ピクセル上が中心）。名前はその分（20＋6 ピクセル）右から始まる。`gauge.py` の見出しのアイコンを置く処理を `load_mark`・`paste_mark` に分けて共用した（利用枠の画面は、3.5 インチ・5.2 インチ、Antigravity を足した画面とも、1 ピクセルも変わらないことを確かめた）
- **横置きでは、名前が監視の状態の帯にかかっていた**（ロゴを付ける前から）。横置きは名前と監視の状態が同じ行にあり、帯は 116〜364 ピクセルの固定だった。見本の `example.com`（15 ピクセルの W6 で幅 106 ピクセル、20〜126）は、赤の状態で末尾が帯に隠れ、取得に失敗したときの文言とも重なっていた（README の `monitor-alert.png` に「example.co」まで写っていた）。名前の右端＋8 ピクセルが帯の左端を越えるときは、帯と文言を右へ寄せるようにした（`monitor_screen.TITLE_GAP`）。名前が短いときと縦置き（帯は名前の下の行）は 1 ピクセルも変わらないことを確かめ、README の横置きの 2 枚を作り直した

### 4-14. サーバーの状態の画面の横置きを、数字をリングの中に入れる形にした（2026-10-15）

- **きっかけ**: ユーザーが「縦画面は変えずに、横画面にした場合の画像を」と求め、数字をリングの中に入れた見本を 2 通り描いた（いまの値と、`--demo alert` の値）。案 1 は 2×2 のまま、リングの右に名前としきい値。案 2 は 5.2 インチと同じ 4 つの縦の列（上から名前・リング・しきい値。列の幅が 120 ピクセルなのでリングは半径 47 に縮む）。**ユーザーが案 1 を選び、実機の画面を書き換えるよう指示した**（17:07）
- `monitor_screen.LANDSCAPE` の値だけを変えた。リングは区画の (58, 69) を中心に半径 52・太さ 11（前は (52, 68)・48）。数字はリングの中に 30 ピクセル（% は 14）で中央にそろえる（前はリングの右に 40 ピクセル）。名前は 18 ピクセル（前は 15）、しきい値は 14 ピクセル（前は 12）で、どちらも縦置きと同じ大きさ。左の列の「しきい値 80%」の右端は 238 で、区切り線（240）の 2 ピクセル手前（2 桁の整数のしきい値まで収まる）
- 確かめたこと: 新しい横置きが見本の案 1 と、縦置きが変更前のコードと、正常・異常・ジョブの障害の見本の値で、架空の設定・実際の設定のどちらでも 1 ピクセルも違わない。テストは 144 件すべて通過。足したテスト（`test_landscape_puts_the_number_inside_the_ring`）は、変更前の配置に戻すと落ちる。README の横置きの 3 枚を作り直した（縦置きの 1 枚は、描いた時刻の数字のほかは同じだったので変えていない）
- この時点では横置きの見出しの行は変えず、監視の状態と右上の時刻は 13 ピクセルのままだった（縦置きは 2026-10-11 に 18・16 ピクセルにしてある）。見本を出したときにユーザーへ伝えた
- 常駐を横置きで登録し直した（17:08。`scripts/install-launch-agent.sh --monitor --device 3.5 --brightness 25`。縦置きの `--portrait --flip` を外した。3.5 インチの横置きは `--flip` 無しで正しい向き（§5-6 の 4））
- **実機を見たユーザーが「ヘッダーの監視状況、更新時刻のフォントサイズが小さくて読みづらい」と指摘した。**見本を 2 案描いた。案 A は見出しを 1 行のまま文字だけを縦置きと同じ大きさにする。案 B は縦置きと同じく監視の状態を名前の下の行に移し、2×2 を 28 ピクセル下げる（リングの半径 52→50）。案 B ならアラートも横幅いっぱいの帯に 18 ピクセルのまま収まると伝えて案 B をすすめたが、**ユーザーは案 A を選んだ**
- 案 A: 監視の状態 13→18 ピクセル、点の半径 4.5→6、帯の中のアラート 15→18 ピクセル、右上の時刻 13→16 ピクセル、帯は 6〜32 → 4〜34。帯の幅（116〜364）は変えていないので、長いアラートは帯に合わせて縮む（見本の「トップ HTTP 503（期待 200）　ほか 1 件」は 18 ピクセルでは収まらない）。時刻（「00:00 更新」の幅 84）の左端は 376 で、帯の右端との間は 12 ピクセル（テスト `test_landscape_stamp_stays_right_of_the_pill`）。見本の案 A と、正常・異常・ジョブの障害・取得の失敗の見本の値で 1 ピクセルも違わず、縦置きは変わらないことを確かめた。README の横置きの 3 枚を作り直した
- ユーザーが実機を見て「サーバー監視状況のモニターはこれでOK」と確定した（17:15 ごろ）

### 4-15. この Mac の状態の画面（2 台目の 3.5 インチ）の設計で決まったこと（2026-10-15）

ユーザーが 2 台目の 3.5 インチを注文した（16:12）。この Mac（Mac mini M4・`Mac16,10`、メモリ 32 GB）の状態を出す画面で、まだ作っていない。設計で決まったことを残す。

- **リングは 4 つ: CPU・メモリ・ディスク（内蔵）・SSD（外付けの `/Volumes/SSD`、4 TB）。**4 つ目をスワップにするか SSD にするかを聞かれ、SSD をすすめた。理由は次のとおり
  - Apple が判断の基準にしているのは、スワップの量ではなくメモリプレッシャーの色（緑・黄・赤。黄は「いずれ RAM が足りなくなる可能性」、赤は「RAM が足りない」。https://support.apple.com/guide/activity-monitor/check-if-your-mac-needs-more-ram-actmntr34865/mac ）。メモリプレッシャーはスワップの頻度などから決まる（https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac ）ので、スワップのリングはメモリのリングと重なる
  - 赤のときに Apple が示す対処は RAM を足すことだけだが、M4 の Mac mini はメモリを購入時に選び、32 GB が上限（https://support.apple.com/en-us/121555 ）。この Mac はすでに 32 GB なので、できるのはメモリを多く使うものを閉じることだけ
  - 10/10〜10/15 のメモリ不足の報告（`JetsamEvent-*.ips`）9 件は、どれも `stickersd` が自分の上限を超えた（`per-process-limit`）もので、Mac 全体の不足ではない。一方、今朝の再起動の前の約 7.4 日で、スワップへの書き出しは 10,204,950 ページ（約 167 GB。`WindowServer-2026-10-15-091656.ips` の `swapouts`）。今朝のフリーズの原因はスワップではない（§4-12）
  - スワップはリングにせず、見出しの下の行でメモリの逼迫を警告するときに量を添え、常駐のログに記録し続ける案を出した
- **向きは横置き。配置は `monitor_screen.LANDSCAPE` と同じ**（数字をリングの中、名前と下の行をリングの右。見出しは §4-14 の案 A の大きさ）。ユーザーが見本で、2×2 の案（案 1）を選んだ。5.2 インチと同じ 4 つの縦の列の案（案 2）は選ばれなかった
- **下の行はしきい値ではなく量**（15:56 にユーザーが選んだ）。表記はスラッシュの前後に空白を入れない（「14.1/32 GB」「327/494 GB」「1.6/4.0 TB」）。空白を入れると、左の列の「327 / 494 GB」（14 ピクセルで幅 98）が区切り線（240）を越える（右端 244）。詰めると右端 235
- **CPU の下の行は「性能 N%」「効率 N%」の 2 行**（ユーザーが「今のままでいい」と決めた）。性能は高性能コア 4 つ、効率は高効率コア 6 つの使用率の平均（`host_processor_info` の CPU ごとの値。デバイスツリーの `cluster-type` で cpu0〜5 が E、cpu6〜9 が P であることを確かめた）。1 行の「性能 31%・効率 32%」は区画に収まらず縮むので 2 行にした
- **名前と 1 行目の位置は、サーバーの画面と同じ**（`LANDSCAPE.label`・`threshold`。CPU の 2 行目は 18 ピクセル下）。CPU だけ 2 行あるため、区画ごとに文字のまとまりを縦の中央にそろえると、CPU とメモリの名前の高さがずれた（ユーザーが指摘）。名前を 9 ピクセル上げる案も見せたが、2 台を並べたときに高さがそろうこの案をユーザーが選んだ
- 値の取り方（どれも管理者権限なしで読める。見本を描いたときに使った）: メモリは `100 - kern.memorystatus_level`（量は 32 GB×割合）。ディスクと SSD は `volumeAvailableCapacityForImportantUsage`（スナップショットなど自動で空く分を空きとして数える。内蔵は 494 GB 中 327 GB で 66%、空きをそのまま数えると 77%）
- 見出しの下の行は、最後のバックアップの時刻（「バックアップ 8:33」、緑）。読み方と、異常のときに出す候補（メモリの逼迫の段階、熱による性能の制限、SSD の状態）は、同じ日に別の会話で調べてユーザーが了承した（16:23）
- **リングの色を変えるしきい値**（ユーザーが推奨どおりに決めた。17:2x）。見本ではサーバーのアラームの値（CPU 80・メモリ 85・ディスク 90）を仮に借りていたので、項目ごとに根拠を調べ直した。オレンジはしきい値の 15 ポイント手前から（サーバーの画面と同じ）
  - CPU: 80%。更新の間隔（1 分）の平均で判定する（一瞬の値だと短い山でも赤になる。サーバーの CPU も 1 分の平均で 80%）。Apple に CPU の使用率の目安の資料は無い
  - **メモリ: 割合のしきい値を使わず、`kern.memorystatus_vm_pressure_level` で色を変える**（2 警告でオレンジ、4 危険で赤。弧の長さは使用率のまま）。macOS（圧縮が有効）の逼迫の段階は、圧縮されずに残っているメモリが圧縮のしきい値を下回るかで決まり（xnu-12377.1.9 の `osfmk/vm/vm_pageout.c` の `VM_PRESSURE_NORMAL_TO_WARNING`・`VM_PRESSURE_WARNING_TO_CRITICAL`、10300〜10335 行目）、`memorystatus_level`（画面の割合の元）は使われていないため、固定の割合は macOS の判定と一致しない。アクティビティモニタのメモリプレッシャーの色（緑・黄・赤）と同じ考え方にそろう
  - ディスク（内蔵）: 90%（自動で空く分を空きとして数えた値で、赤は空き 49 GB 未満、オレンジは 124 GB 未満）。macOS のアップデートに要る空きは Apple の「How to download and install macOS」（https://support.apple.com/en-us/102662 ）に書かれておらず、Apple 以外の資料では 35〜60 GB（大学の案内で 50 GB など）。赤の境目はその範囲に入る
  - SSD: 90%（赤は空き 400 GB 未満、オレンジは 1 TB 未満）。データを置くだけなので OS としての必要量は無く、使い方で決める値。95% も選べると伝えた
- 2 台目は USB のシリアル番号が 1 台目と同じ `USB35INCHIPSV2` なので、挿す USB の位置で見分ける作りになる（別の会話が `ioreg` で確かめた）。届いたら、2 台目のシリアル番号を `system_profiler SPUSBHostDataType` で確かめる
- **実装した**（2026-10-15、ユーザーの指示「元のセッションが行方不明。実装はこのセッションで進めて」。設計を決めた会話のプロセスが 16:44 に止まったため、この会話で作った）
  - `local` コマンドと常駐（`__main__.LocalRunner`。`MonitorRunner` を土台に、取得と描画の呼び出しだけを差し替える）、値の取得と組み立ては `local_monitor.py`。`monitor_screen.render` に、下の行の文言（`MetricValue.detail`。2 行目は `DETAIL_LINE`＝18 ピクセル下）、リングの色の決め打ち（`MetricValue.tint`）、異常が無いときの見出しの文言（`note`）を足した。どれも省けば前のとおりで、サーバーの画面は、見本の値・向き・取得の失敗の組み合わせ 26 通りで変更前と 1 ピクセルも違わないことを確かめた
  - 同じ機種の 3.5 インチを USB の位置で選ぶ `--location`（`test-pattern`・`run`・`monitor`・`local`）。位置は macOS の Location ID（上の 8 ビットがバス、続く 4 ビットずつが端子の番号）で、pyusb の `bus`・`port_numbers` から組み立てた値が、この Mac の 17 台で `ioreg -p IOUSB` と一致した。`probe` が位置を出し、3.5 インチは位置ごとに確保を試す
  - CPU の番号と種類の対応を実測で確かめた: `taskpolicy -b`（バックグラウンドの優先度。高効率コアで動く）で `yes` を 4 つ動かすと、`host_processor_info` の 0〜5 番だけが 87% 前後に上がり、6〜9 番は 27% 前後のままだった。デバイスツリーの `cpu0`〜`cpu5` が E であることと一致する
  - `host_processor_info` の結果はカーネルが割り当てたページに入るので、`vm_deallocate` で返している（返さないと 1 分ごとに 1 ページずつ増え続ける）
  - TimeMachineEditor の「Last run」は、成功したときだけ更新される（`/Library/Logs/TimeMachineEditor/scheduler.log`。10/15 の夜中の 5 回の失敗の間は 10/14 9:19 のままで、8:35 に更新された）。失敗した試行は「Last try」
  - 熱の段階は、公開ヘッダー `libkern/OSThermalNotification.h` の通知（`kOSThermalNotificationPressureLevelName`）で読む。macOS の値は 0 Nominal・1 Moderate・2 Heavy・3 Trapping・4 Sleeping で、2 から見出しに出す（Moderate で出すかは決めていなかったので、性能の制限がはっきり起きている Heavy からにした）。バックアップが古いとみなすのは 36 時間（毎日のバックアップが 1 回抜けたら気付けるように）。この 2 つはユーザーに確かめていない値で、README に書いた
  - テストは 165 件すべて通過（足したのは、`tests/test_local_monitor.py` の 13 件、描画 3 件、USB の位置 1 件、常駐 2 件、引数 1 件）
  - launchd から `local --preview` を 1 回だけ動かして確かめた（18:08。確かめ用の LaunchAgent は、終わってから外した）。Time Machine の設定ファイルは `PermissionError` で読めず、`tmectl info` の時刻（8:35）が見出しに出た。`run`・`monitor` の常駐も新しいコードで起動し直し、どちらも接続を待つ状態で動いている（新しいモジュールは起動時に読み込まれるため）
  - 実機ではまだ表示していない。2026-10-15 17:31 に 2 台のディスプレイ（3.5 インチと 5.2 インチ）がどちらも USB から外れ（ログ「ディスプレイが外れました」）、実装を終えた時点でもつながっていなかったため
- **最後のバックアップの時刻の読み方を、`tmectl` からバックアップ先のスナップショットの名前に変えた**（2026-10-16）。ユーザーが TimeMachineEditor をアンインストールし、macOS の自動バックアップ（1 時間ごと）に戻すと決めたため
  - きっかけ: 夜中（3:00〜）のバックアップは毎晩失敗し、朝に Mac を使い始めた後の試行だけが成功していた。10/16 の Time Machine のログでは、3:28〜3:47 に「ロック中は読めない項目」（`unreadable while device locked`。位置情報の学習・LINE・音声認識の一時ファイル）の記録があり、4:07:12 に `Backup failed: BACKUP_FAILED_DEVICE_LOCKED (80)` で失敗した。TimeMachineEditor の記録では 3:00〜4:59 に操作が無く、5:07 の試行（操作のある時間に重なった）は 6:29 に成功した
  - launchd から読めるかを、確かめ用の LaunchAgent で確かめた: `tmutil latestbackup` は「requires Full Disk Access」で読めない。`tmutil destinationinfo`（バックアップ先の Mount Point）と `diskutil apfs listSnapshots /Volumes/backup`（`com.apple.TimeMachine.2026-10-16-062646.backup` のような名前。この Mac の時刻）は読める。設定ファイルの `SnapshotDates` と同じ時刻（6:26:46）が得られ、launchd から `local --preview` を動かすと見出しに「バックアップ 6:26」が出た
- **見出しの Apple のロゴ**（2026-10-20、ユーザーの指示「apple のロゴを入れたい」）。`local` に `--logo`（画像のパス。無ければ引数の解析で止める）を足し、サーバーの状態の画面の `logo` と同じ描き方（20 ピクセル角の枠、名前の字の高さの中ほど）で名前の左に出す
  - 画像は、macOS の SF Pro（`/System/Library/Fonts/SFNS.ttf`）の U+F8FF（Option-Shift-K で打てる Apple のロゴの文字）を、512 ポイントで白一色・背景透明に描き、周りの透明な余白を切って作った（316×388 ピクセル）。`~/Library/Application Support/claude-usage-display/icons/apple.png` に置いた。この文字を持つフォントは、SFNS・SFNSRounded・SFCompact・Helvetica・HelveticaNeue・LucidaGrande だった（ヒラギノ角ゴシック・Apple Symbols・Menlo は、存在しない文字と同じ形になる）
  - **画像はリポジトリに入れない**（Claude・Gemini のロゴと同じ扱い）。Apple の「Guidelines for Using Apple Trademarks and Copyrights」（https://www.apple.com/legal/intellectual-property/guidelinesfor3rdparties.html 、Unauthorized Use の 2）は、Apple のロゴやアイコンを、書面による商標のライセンス（販売店契約など）による場合を除き、どの目的にも使えないとしている。ユーザーに伝えた。README の画像・テストは `--logo` を付けずに作る（テストは白い四角の見本を使う）

### 4-16. 利用枠の常駐が `run --help` に置き換わり、5.2 インチが一晩点いたままだった（2026-10-17）

- **気付いたこと**（05:00 ごろ、起きたユーザーが報告）: Mac の画面は消え、3.5 インチも消えていたが、5.2 インチは点いたままだった。3.5 インチは正しく動いていた（ログ: 00:46:20「席を離れたので消灯しました（無操作 10 分）」、05:04:11「操作が戻ったので点灯しました」）
- **原因**: 2026-10-16 22:16:21、別の会話（サーバーの画面の確認済みの障害を足した作業。`d2e7c11`）が、テストの後に `scripts/install-launch-agent.sh --help >/dev/null 2>&1` を実行した。スクリプトは登録の前に本物の引数解析を通してオプションを確かめるが、argparse は説明を出すと 0 で終わるため、誤りなしとみなして `run --help` を常駐として登録した（`~/Library/LaunchAgents/jp.co.studioc.claude-usage-display.plist` の更新時刻 22:16）。出力を捨てていたので、その会話は気付いていない
  - 前の常駐は 22:16:24 に SIGTERM で終わった。終わるときに画面を消さない作りだったので、5.2 インチは 22:16 の画面を明るさ 40 で約 6 時間 50 分出し続けた
  - `run --help` は説明を出して 0 で終わり、launchd（`KeepAlive`）が約 10 秒ごとに起動し直した（ログに説明が 2,406 回）。ディスプレイを開かないので、席を離れたときの消灯も効かなかった
  - `DRY_RUN=1` で再現した: 直す前のスクリプトは `--help` でも省略形の `--he` でも plist を作った
- **ユーザーの指示で次を行った**
  - 前の登録（`scripts/install-launch-agent.sh --device 5.2 --brightness 40 --icons "$HOME/Library/Application Support/claude-usage-display/icons"`）に戻した（05:12:45 に接続）
  - 登録スクリプト: 引数の確かめで `SystemExit(0)`（コマンドの本体まで進まずに説明を出した）を見分け、「説明を表示しただけで、登録は変えていません」と出して 0 で終わる（`tests/test_install_script.py`。`DRY_RUN=1` で動かすので登録はしない）
  - **3 つの常駐とも、終わるときに画面を消してから閉じる**（`_Resident._shutdown`。消灯中なら消し直さない。外れていれば黙って閉じる）。ユーザーが推奨どおりに決めた
  - 3.5 インチの初期化（`TuringRevA.initialize`）で `SCREEN_ON` も送る。前のプロセスが終わるときに `SCREEN_OFF` で消すため。`SCREEN_OFF` の後に明るさの命令だけで点くかは確かめていない
- **確かめたこと**: テストは 173 件すべて通過。終わるときに消すテストは、直す前の閉じ方に差し替えると落ちる。実機では、05:15〜05:16 に 2 つの常駐を `launchctl kickstart -k` で 2 回ずつ起動し直した（1 回目で新しいコードを読み込み、2 回目で「終わるときに消す → 次の起動で点ける」を通す）。2 回目の停止で 5.2 インチの常駐の終わりまでが 17 ミリ秒から 92 ミリ秒に延び（黒の画像と明るさ 0 の分）、どちらもエラーなく接続し直した。05:16:31 に利用枠の常駐を `launchctl bootout` で外すと、5.2 インチは真っ暗になり、3.5 インチは（消してから起動し直した後に）サーバーの状態の画面を出していることを、ユーザーが実機で確かめた。05:16:59 に同じ plist で読み込み直した
- **登録スクリプトを確かめるときは `DRY_RUN=1` を付ける。**付けずに実行すると、`--help` 以外は本当に登録し直す

### 4-17. 監視の障害の見出しに、件数だけでなく名前と理由を出した（2026-10-22）

- きっかけ: ユーザーの指摘「実際に障害じゃないのに出てるケースが多い。このままだと表示されても見なくなる」。サービス側で過去 15 日の障害の表示 8 回を調べると、サービスが実際に壊れていたのは 1 回だけで、残りは監視の設定の配り直し待ちや、ジョブの中身の様子だった。見出しは「監視の障害 1 件」としか出さないため、毎回状態ファイルを読まないと見分けられなかった
- 見出しの注意: 1 件なら「名前: 理由の最初の文（括弧の中を除く）」、複数なら「件数（先頭の名前 ほか）」。名前は `state.names` → 状態ファイルの項目の `name` → ID の順で選ぶ（サービス側の監視が 2026-10-22 から `name` を書く）。20 文字を超えたら切る（480×320 では長い名前で文字が最小まで縮み、右の時刻に重なった）
- サービス側の是正（監視の設定の配り直しの自動化・ジョブの失敗の区分）は、そのサービスの非公開のリポジトリに記録した


### 4-18. 見出しの名前を出さず、異常の文言を大きくする設定（2026-10-22）

- **経緯**: 実機のサーバーの状態の画面（3.5 インチ・横置き）で、監視の障害の見出し（「名前: 理由」）が、名前の右の帯（幅 248 ピクセル）に収めるため 10 ピクセル前後まで縮み、読めなかった（ユーザーの指示「エラーが小さくてかなり読みづらい。見出しの名前のテキストを消して、もっと大きいフォントサイズでエラー表示したい」）
- **決めたこと**: `monitor.toml` の `show_title = false`（既定 true）で、横置きの見出しの名前を出さず、帯と文言を名前の分だけ左へ広げる（ロゴと右上の時刻は残す）。異常の文言（赤の画面のアラートも、オレンジの警告も）は、1 行なら 24 ピクセル、収まらなければ 2 行にして 21 ピクセルから 17 ピクセルまで収まる最大の大きさにする。2 行に分ける位置は、「名前: 理由」・「…　ほか N 件」・「件数（名前 ほか）」の順に探し、どこでも収まらなければ字数で折り返して 2 行目を「…」で切る（`monitor_screen._big_lines`）。赤の画面の 2 行は、白い帯を 4〜54 ピクセルに広げる（区切り線の始まり 56 ピクセル・リングの上端 61 ピクセルの手前）
- **縦置きには効かない**（縦置きは見出しの行が別の配置で、2026-10-11 に大きくした経緯がある）。「監視 正常」は従来の大きさ（18 ピクセル）のまま
- 見本は `tests/test_monitor_screen.py` の `HiddenTitleTest`（分け方・縦置きが変わらないこと）

## 5. 残っている作業（上から順に）

1〜5 は 2026-10-05 に終えた（README.md、CLAUDE.md、requirements.txt と .gitignore、自動起動の作成と登録、git の初期化と push）。

6. **ディスプレイが届いたら**（外部要因。到着が再開の条件）。作業はすべて `~/projects/claude-usage-display` で行う。画面を見て判断する段階は、ユーザーに見てもらう
   1. **つなぐ前に、自動起動を止める**（2026-10-09 済み）: `scripts/uninstall-launch-agent.sh`（「停止しました」「解除しました」と出る）。登録したままつなぐと、常駐の `run` がすぐ送信を始め、確認用のコマンドと同じパネルへ同時に書く。パネルは画素を数えながら受け取るので、2 つのプロセスが書くと画面が崩れる（§4-3）
   2. **つないで機種を確かめる**（2026-10-09 済み。rev A。§4-7）: USB-C でつなぎ、`system_profiler SPUSBHostDataType | grep -B8 -A2 'USB Product ID: 0x5722'` を実行する。`USB Vendor ID: 0x1a86`・`USB Product ID: 0x5722`・`Serial Number: USB35INCHIPSV2` が出れば rev A
      - 何も出なければ、ケーブルがデータ通信に対応しているかを確かめる。別の ID なら rev A ではないので、§4-3・§4-4 の前提から見直す
      - **ID が同じでもシリアルが `2017-2-25` なら XuanFang の rev B** で、通信方式が違う（`lcd_comm_rev_b.py` 75・77 行目）。rev A 用の以降の手順には進まない（`turing.py` はシリアルを見ずに ID だけで開き、rev A の命令を送るため）。rev B の通信方式を `turing.py` に足してから進める。違いは次のとおり（いずれも `lcd_comm_rev_b.py`）
        - 命令は 10 バイト（先頭と末尾にコマンド番号、中に 8 バイト。82〜99 行目）。番号は HELLO 0xCA・SET_ORIENTATION 0xCB・DISPLAY_BITMAP 0xCC・SET_LIGHTING 0xCD・SET_BRIGHTNESS 0xCE（29〜34 行目）
        - 最初に HELLO を送り、10 バイトの応答で型番の細分（A01・A02・A11・A12）を判定する（105〜139 行目）。rev A と違い、応答を読む
        - 明るさは A11・A12 が 0〜255 で 255 が最も明るい（rev A と逆）。A01・A02 はオンかオフだけ（45〜49・168〜179 行目）
        - 向きはパネルが縦と横だけを持ち、上下逆はソフトで 180 度回す（189〜197 行目）
        - 画素は RGB565 のビッグエンディアン（203 行目）。幅×8 バイトずつ送り、送り終えたら 0.05 秒あける（249〜259 行目）
        - macOS: rev B 系（flagship）は、ライブラリの送信の競合を直して間を置くと安定したという報告がある（issue #7、gerph、2022-09-01、PR #34）。libusb で直接書く方式が rev B でも要るかの報告は無いので、実機で確かめながら作る
   3. **インターフェースを確保できるか**（2026-10-09 済み。§4-8）: `.venv/bin/python -m claude_usage_display probe`。最後に「インターフェースを確保できました」と出れば次へ。確保できない場合は、表示されたエラーをそのまま記録し、それをもとに対処を調べる。シリアル（`/dev/cu.usbmodem…`）での送信に切り替えない（§4-3。gist の報告者は確保できている）
   4. **向きと色**（2026-10-09 済み。`--flip` は要らない）: `.venv/bin/python -m claude_usage_display test-pattern`。正しければ、左上が赤で「左上」、右上が緑で「緑」、左下が青で「青」、右下が白、中央に「480×320」が出る
      - 上下が逆なら `test-pattern --flip` で確かめ直す。以降のコマンドにも `--flip` を付ける
      - 赤と青が入れ替わっていたら、`turing.py` の `to_rgb565le` の並びを見直す
   5. **1 画面の転送時間を測る**（記事の素材。2026-10-09 済み。約 1.87 秒）。次を実行する（2026-10-05 に、未接続の検出まで動くことを確認済み。上下が逆なら `TuringRevA(UsbTransport.open(), flipped=True)` にする）
      ```
      .venv/bin/python - <<'EOF'
      import time

      from claude_usage_display.render import render_test_pattern
      from claude_usage_display.turing import DeviceNotFound, TuringRevA, UsbTransport, to_rgb565le

      frame = to_rgb565le(render_test_pattern())
      try:
          display = TuringRevA(UsbTransport.open())
      except DeviceNotFound as e:
          print(f"未接続の検出まで動作: {e}")
          raise SystemExit(0)
      try:
          display.initialize(30)
          times = []
          for _ in range(5):
              start = time.perf_counter()
              display.show_frame(frame)
              times.append((time.perf_counter() - start) * 1000)
          print("1 画面の転送: " + " / ".join(f"{t:.0f}" for t in times) + " ミリ秒")
      finally:
          display.close()
      EOF
      ```
   6. **実際の画面を数分動かす**（2026-10-09 済み。文字の色と太さを直し、ユーザーが実機で確定した。明るさは既定の 30 のまま。§4-8）: `.venv/bin/python -m claude_usage_display run --save-png /tmp/claude-usage-last.png`（Ctrl+C で終了）。画面と保存した画像が一致することを確かめる。ユーザーに次を見てもらう
      - ゲージ型の細部: リングの縁、灰色の文字の読みやすさ、カードの面と黒地の差
      - 明るさ: 既定は 30。`--brightness 20`・`--brightness 50` などで見比べる
      - 合わなければ `--theme classic` と見比べる
      - 記事用の写真は、実際の利用枠が写らないよう、見本の値（26%・74%・93%）の画面を送ってから撮る（2026-10-09、ユーザーは実際の利用枠が写った写真 `IMG_4337.jpeg` を記事に使うと決めた。`docs/article-material.md` §12 の 5）。`run` を止めてから次を実行する（2026-10-05 に、未接続の検出まで動くことを確認済み。上下が逆なら `flipped=True` を付ける）
        ```
        .venv/bin/python - <<'EOF'
        from datetime import datetime, timezone

        from claude_usage_display import gauge
        from claude_usage_display.__main__ import _demo_snapshot
        from claude_usage_display.turing import TuringRevA, UsbTransport

        now = datetime.now(timezone.utc)
        display = TuringRevA(UsbTransport.open())
        try:
            display.initialize(30)
            display.show(gauge.render(_demo_snapshot(now, "Fable"), now))
        finally:
            display.close()
        EOF
        ```
   7. **自動起動を登録し直す**（2026-10-09 08:22 に既定のオプションで登録し、ログで接続を確認済み。ログアウトしてログインし直したあとの表示は、ユーザーが次にログインし直したときに確かめる）: `scripts/install-launch-agent.sh`。手順 4・6 で決めたオプションがあれば付ける（例: `scripts/install-launch-agent.sh --flip --brightness 40`）。ログアウトしてログインし直したあとも表示されることと、`~/Library/Logs/claude-usage-display.log` に「ディスプレイに接続しました」が出ることを確かめる
   8. **Mac 本体の USB-C 端子で電源が入らない原因を確定させる**（2026-10-09 済み。§4-7）: L 字アダプターなし・両方の向きで入らないことを確かめたうえで、同じ USB-C⇔USB-C ケーブルで iPhone を本体の USB-C 端子につなぎ、認識されることを確かめた（08:58）。ケーブルの CC と本体の端子は正常で、原因はディスプレイ側の USB-C 端子（Rd を示していない）と確定した
7. **実機で分かったことを書き残す**: 確保の可否、向き、色、明るさ、転送時間、ゲージ型の見え方、写真を、`docs/article-material.md` §10 に書く。作業の判断に関わること（エラーと対処など）は、この文書の §4 にも追記する
8. **公開と記事**（2026-10-09 済み）: 認証の扱いは「今の方式のまま公開し、README と記事に規約上の位置づけを明記する」とユーザーが決めた。README に規約上の位置づけを書き（`0e10883`）、§6 の確認（履歴にトークン・個人のアドレス・IP・API の生の応答が無いこと）をしてから public にし、記事を公開した（https://studioc.co.jp/tech/claude-code-usage-on-mac-usb-display/ 、タイトル「Claude Codeの利用枠を3.5インチ外部モニターに出力した」、studioc の `0abfec0`）。記事はユーザーの指示で、このリポジトリで起動したセッションが studioc の `.claude/skills/techblog-write/SKILL.md` と `docs/tech_blog_writing_guide.md` を読んで同じ手順で書いた。公開日はユーザーの指示で当日（金曜。火曜・木曜の枠の外）。X への告知はユーザーが手動で行う（定時の `x-announce.yml` は朝 7:00 に当日分だけを告知するので、この記事は自動では告知されない）。当初の手順は次のとおり: §6 の「認証の扱い」を決める → 必要なら実装を直す → README に、規約上の位置づけと、公式に説明されていない API を使っていることを明記する（2026-10-09 ユーザーが決定。`docs/article-material.md` §12 の 10）→ リポジトリを public にする → `~/projects/studioc` で起動したセッションが `/techblog-write` で記事を書く（素材は `docs/article-material.md`）
9. **5.2 インチのディスプレイ**（**2026-10-09 12:40 ごろ、ユーザーが注文した**。AliExpress 1005010058380485、TURZX 5.2" 1280×720、Option 1-Black、5,541 円（9%OFF）、配達予定 10 月 17〜21 日。付属品の画像に USB-A と USB-C の端子が付いたケーブルがあるので、USB ハブの USB-A 端子につなぐ。届くのが再開の条件）。当初は 5 インチ（rev C、1005011742654881）を検討したが、macOS で動かす関門が少ない新しい世代の 5.2 インチに替えた（§4-9）。到着から 90 日以内なら返送料なしで返品できる（§4-9）
   **2026-10-15 に届き、1・2 を終えた（§4-11）。いまの登録は `scripts/install-launch-agent.sh --device 5.2 --brightness 40 --icons "$HOME/Library/Application Support/claude-usage-display/icons"`（見出しに Claude Code のキャラクター。§4-11）。返品はしない（通信できたため）。記事は 2026-10-15 に公開した（https://studioc.co.jp/tech/claude-code-usage-on-52-inch-usb-display/ 。`docs/article-material.md` §13）**
   1. **届いたら最初に、Mac で通信できるかを確かめる**（返品の判断はここで決まる）。送信部（`turzx_usb.py`）は 2026-10-09 に先に書いた。見出しのバイト列は phstudy の実装と一致することをテストで固定してある（`tests/test_turzx_usb.py`）
      1. 自動起動を止める（`scripts/uninstall-launch-agent.sh`）。3.5 インチは外す（両方つながっていると 5.2 インチを使うが、確かめる間は 1 台にする）
      2. USB-A のハブにつなぎ、`.venv/bin/python -m claude_usage_display probe`。`1cbe:0050 TURZX 5.2 インチ` と出て、「インターフェースを確保できました」で終われば次へ。別の ID なら、中身の世代が違う個体（§4-9 の #727）。一覧の出力をそのまま記録する
      3. `.venv/bin/python -m claude_usage_display test-pattern`。命令 10（同期）・14（明るさ）・102（PNG）の応答が表示される。先頭が「命令番号 c8 時刻 4 バイト」なら想定どおり。違う形なら、表示された応答を記録し、`turzx_usb.check_response` を実機に合わせて直す（明るさの命令に応答が無いことも考えられる。ライブラリは明るさの応答を確かめていない）
      4. 画面に確認画面が出るか、左上が赤で「左上」か（逆なら `--flip`）、1280×720 と出るかを見る
   2. 通信できたら: `run` で動かす（ゲージ型は 1280×720 で描く。2026-10-09 に先に作り、ユーザーが見本の画像で確かめて決めた。見本は `docs/images/gauge-1280x720.png`。2026-10-11 に Gemini の枠とアイコンを足した（§4-10）。いまの登録は `scripts/install-launch-agent.sh --device 5.2 --brightness 25`。Antigravity の枠は出さない（§4-10））→ 実機で文字の大きさ・色・明るさを見てもらい、必要なら調整する → 自動起動で動かす → 別の記事にする（`docs/article-material.md` §12 の 4）
   3. 通信できなかったら: 到着から 90 日以内に返品する（ユーザーが判断する）

10. **サーバーの状態の画面（`monitor`）**（2026-10-10 にユーザーの指示で作った。3.5 インチを、会社のサービスのサーバーの監視に使う）
    - 画面の設計はユーザーが見本の画像で決めた: 案 3（2×2、小さなリングと大きな数字）。しきい値の行は「しきい値 80%」とだけ書く。サイトとサーバーの異常のときは画面全体を**明るい赤**（気付くことを優先）。ジョブの障害と監視の設定のずれは、赤にせず見出しにオレンジで件数（障害が何日も続くものがあり、赤が出っぱなしになると本当の異常を見落とすため）。死活は、この Mac から問い合わせず、AWS で動く既存の外形・死活監視の判定（S3 の状態ファイル）を使う（この Mac のネットワークが切れたときに誤って赤くしないため）
    - 読み取り専用の IAM ユーザーを作り、鍵をこの Mac の Keychain に置いた。陽性（メトリクスと状態ファイルが読める）と否定（書き込み・アラーム・バケットの一覧・ほかのファイル・ほかのサービスが拒否される）を確かめた。作成の手順とユーザー名は、そのサービスの非公開のリポジトリにある（このリポジトリは public なので書かない）
    - `monitor.toml`（この Mac にだけある）で、実際の値で画面を描けることを `monitor --preview` で確かめた（2026-10-10 12:36）
    - **2026-10-11 0:42 に、ユーザーの指示で 3.5 インチをサーバーの状態の画面に切り替えた。**利用枠の常駐は `scripts/install-launch-agent.sh --device 5.2` で登録し直し（5.2 インチが届くまで接続を待つだけで、API は呼ばない）、サーバーの状態の常駐を `scripts/install-launch-agent.sh --monitor --device 3.5` で登録した（ログは `~/Library/Logs/claude-usage-display-monitor.log`）。0:42:25 に接続し、画面の送信まで済んだ。**5.2 インチが届くまで、利用枠はどの画面にも出ない**
    - **縦置きにした**（2026-10-11 0:58、ユーザーの指示）。見本の画像で案 B（名前の下にリング、リングの中に数字の 2×2）を選んだ。実機で `test-pattern --portrait` を送ると天地が逆だったので、`--flip`（縦の逆、命令の値 1）で正しいことをユーザーが確かめた。いまの登録は `scripts/install-launch-agent.sh --monitor --device 3.5 --portrait --flip --brightness 25`（明るさは、ユーザーの「少し暗くしたい」で既定の 30% から 20% にし、続く指示で 25% にした。ユーザーが実機で確かめて 25% に決めた（2026-10-11 10:08）。rev A のパネルの値は 255 − 明るさ × 255 ÷ 100 で、30% は 178、25% は 191（255 − 63.75 の小数を切り捨てる）、20% は 204）
    - 実機を見たユーザーの指示で、縦置きの名前（15→18 ピクセル）・しきい値（12→14）・リング（半径 46→56、太さ 10→12）・リングの中の数字（30→34）を大きくし、ユーザーが実機で確かめて決めた（2026-10-11 1:00。`monitor_screen.PORTRAIT`）
    - 続けて、見出しの下の監視の状態（「監視 正常」・ジョブ障害の件数）を 13→18 ピクセル（点の半径 4.5→6）、赤の画面の帯の中のアラートを 15→18 ピクセルにした（2026-10-11 2:00、ユーザーの指示）。アラートが 2 件以上のときは、1 行に「ほか N 件」まで詰めると 12 ピクセルまで縮む（変更前も同じ）ので、縦置きだけ帯を 2 行にし、2 行目に「ほか N 件」を出す。横置きは変えていない（変更前のコードと 1 ピクセルも違わないことを確かめた）
    - 右上の取得の時刻を 13→16 ピクセルにし、ユーザーが実機で確かめて決めた（2026-10-11 14:56、ユーザーの指示。`PORTRAIT.stamp_size`）。横置きは変えていない（同じく確かめた）
    - 切り替えの時点で、外形・死活監視の障害は 0 件だった。2026-10-10 22:38 に残っていた 3 件（設定のずれ・ジョブ AI_MODELS・BILLING）は、その後に解消していた（ユーザーに引き継ぎの文章を渡し、そのサービスの開発のセッションに引き継いだもの）
    - **画面全体を赤にする値の条件を、CloudWatch のアラームと同じにした**（2026-10-11、ユーザーの指示。記事を書くセッションが、アラームの設定と比べて見つけた）。直近 1 分の平均がしきい値以上になるだけで赤にしていたため、アラームが「瞬間的な高負荷を拾わない」ために持つ連続の条件（CPU・メモリは 1 分×5、スワップは 5 分×3、ディスクは 1 回）が効いていなかった。使っているサーバーの過去 14 日（09-27〜10-11）の値に当てると、直す前の判定では 14 回（CPU 13・スワップ 1。cron やデプロイの 1〜4 分の山が 12 回）赤になり、アラームの条件に当たるのは 2 回（32 分・16 分の CPU）だった。直した判定では同じ 14 日で 2 回
      - 各メトリクスに `period`（平均を取る秒数）と `datapoints`（続けて超えた回数）を持たせ、`GetMetricStatistics` の `Period` に `period` を渡し、いちばん新しい点から途切れずにしきい値以上が続いた回数（`over_streak`）が `datapoints` に達したら赤にする。間の空いた点は続いていないとみなす。1 回だけの山では、リングだけが赤になる
      - 「値が届いていない」の判定を、`period` が長いときは 2 周期にした。スワップの 5 分ごとの平均は、いちばん新しい点が 5 分を過ぎることがある（直した直後の実測で 5.4 分前）。5 分のままだと、それだけで赤になる
      - 見本の値（`--demo alert`）は、しきい値以上の値を `datapoints` 回続いたものとして描く
      - テスト 103 件すべて通過。判定の 1 行（`metric.sustained`）を直す前の形に戻すと、1 回だけの山のテストと、ディスクとスワップの回数のテストが落ちることを確かめた
      - この Mac の `monitor.toml` にもアラームと同じ値を書き足し、常駐を `launchctl kickstart -k` で再起動した（01:31 に接続）。実際の値で読めて、判定が正常なことを確かめた
    - **確認済みの障害を、その障害が続く間だけ画面から外せるようにした**（2026-10-16、ユーザーの指示「障害が出ていて解決まで待たなければいけないものを出しておく必要がない」）
      - きっかけ: 日次のジョブが 10-16 08:02 から失敗し、「ジョブ障害 1 件」が出続けた。失敗の理由は、ジョブの中の検査が「外のクローラーが 5 日続けて来ない」と判定したことだった。サービス側に止めている設定は無く（エッジの集計で 403 も 0 件、robots.txt は許可）、クローラーが戻るのを待つしかない
      - 出し続けない理由: 監視は障害の状態に入ったときだけ通知し、状態ファイルの理由も開始時刻も、同じジョブが別の理由で失敗しても変わらない。出し続けると、同じジョブの本当の失敗（レポートが送れない等）でも表示が変わらず、ほかのジョブの障害が増えても見落としやすい。ジョブごと常に外す案は、本当の失敗まで消えるので採らなかった
      - 仕組み: `monitor.toml` の `[state.acknowledged]` に、監視の ID と障害が始まった時刻（状態ファイルの `since`。秒まで）を書くと、`assess` がその障害を赤にも件数にも入れない。成功に戻ってから再び失敗すると `since` が変わるので、また出る。`monitor --incidents` が書き写す行と、もう続いていない行を出す。常駐は外した障害をログに残す（「確認済みのため出さない障害: …」）
      - テスト 168 件すべて通過。確認済みの判定を無効にすると、追加した 2 件が落ちることを確かめた。この Mac の `monitor.toml` に今回のジョブを書き、常駐を再起動して、実機の画面が「監視 正常」に戻ったことと、ログを確かめた（22:15）
    - 2026-10-10 1:47:45 に 3.5 インチが USB から外れた（ログ「ディスプレイが外れました」）。12:39 の時点でも USB の一覧に無い。原因はこのセッションでは分かっていない（ユーザーに報告した）。2026-10-11 0:40 にユーザーがつなぎ直し、同じハブの端子（Location ID `0x00111000`）で認識され、利用枠の常駐が 0:40:09 に接続した。0:41 の描き直しもエラーなく送られた
11. **この Mac の状態の画面（`local`）を 2 台目の 3.5 インチで動かす**（2026-10-15 に実装した。§4-15）
    **2026-10-21 に 1〜4 を終えた。**いまの登録は、サーバーの状態が `scripts/install-launch-agent.sh --monitor --device 3.5 --brightness 25 --location 0x00120000`、この Mac の状態が `scripts/install-launch-agent.sh --local --brightness 25 --flip --location 0x01120000 --logo "$HOME/Library/Application Support/claude-usage-display/icons/apple.png"`。挿す端子を変えると位置が変わり、その画面は出なくなるので、`probe` で位置を見て登録し直す
    - 2 台目は、つないだ直後は USB の機器として現れなかった（04:08 の `probe` と `system_profiler SPUSBHostDataType` に 3.5 インチは 1 台だけ。カーネルの記録にも出入りが無い）。`ioreg -p IOUSB` を 0.5 秒ごとに記録しながらユーザーにケーブルを逆に挿してもらうと、04:09:31 に認識されていたほうの 1 台（`0x00120000`）が消えた（逆にしたのはこちらだった）。元に戻して 04:11:03 に `0x00120000` が戻り、もう 1 台を挿し直すと 04:11:13 に `0x01120000` に現れた。1 台目と同じく、挿す向きで認識が変わる（§4-7。L 字アダプターを挟んでいるかは聞いていない）
    - シリアル番号は 2 台とも `USB35INCHIPSV2`（`probe`）。`0x00120000` は Genesys Logic のハブ（`05e3:0610`、`0x00100000`）の 2 番の端子、`0x01120000` は別のバスのハブ（`0bda:5411`、`0x01100000`）の下
    - サーバーの常駐は、04:11:19 に `0x00120000` をつかんでいた（`probe` でこちらだけ確保できない）ので、そのまま位置を固定した。2 台目は、ユーザーの置き方では天地が逆で、`--flip` で正しい向きになった。見出しの「バックアップ 4:04」、CPU の 2 行目（性能・効率）、4 つのリングの色、左上の Apple のロゴを、ユーザーが実機で確かめた（04:13）。明るさは、サーバーの画面と同じ 25%（パネルの値 191）で始めた
    1. 2 台目をつなぎ、`.venv/bin/python -m claude_usage_display probe` で 2 台の「位置 0x…」を控える。シリアル番号が同じ `USB35INCHIPSV2` かも見る
    2. サーバーの状態の常駐を、その 3.5 インチの位置を付けて登録し直す: `scripts/install-launch-agent.sh --monitor --device 3.5 --brightness 25 --location 0x…`（付けないと、2 つの常駐が同じ 3.5 インチを取り合う）
    3. この Mac の状態の常駐を登録する: `scripts/install-launch-agent.sh --local --location 0x… --logo "$HOME/Library/Application Support/claude-usage-display/icons/apple.png"`（明るさはサーバーの画面と見比べて決める。ロゴは §4-15 の「見出しの Apple のロゴ」）。天地が逆なら `--flip`
    4. 実機の画面をユーザーに見てもらう（見出しの「バックアップ …」、CPU の 2 行目、ログ `~/Library/Logs/claude-usage-display-local.log`）

## 6. 公開するときに確かめること

- **認証の扱い（2026-10-05 に調査。公開の可否を左右する）**: このツールは、Claude Code が Keychain に置いた OAuth のアクセストークンを読み、文書化されていない `/api/oauth/usage` を呼ぶ。Claude Code の「Legal and compliance」（https://code.claude.com/docs/en/legal-and-compliance 、「Authentication and credential use」）は次のように定める
  - OAuth 認証は、サブスクリプションの購入者が Claude Code と Anthropic 純正のアプリを普通に使うためのもの（"designed to support ordinary use of Claude Code and other native Anthropic applications"）
  - 製品やサービスを作る開発者は API キーを使う。第三者の開発者が、Free・Pro・Max の資格情報で利用者の代わりにリクエストを流すことは認めない。開発者は Claude.ai の資格情報やセッショントークンを収集・保存・仲介してはならない
  - Anthropic は、これらの制限を予告なく執行できる（"may do so without prior notice"）。用途ごとの可否は sales への問い合わせを案内している
  - このツールは、利用者本人の Mac で本人のトークンを読むだけで、保存も他人への提供もしない。ただし、Anthropic 純正ではないアプリが OAuth のトークンを使う点について、上の文書は許可も禁止も明示していない
  - 公式に渡される別の経路がある: ステータスラインのスクリプトに渡る JSON の `rate_limits.five_hour` / `rate_limits.seven_day`（`used_percentage` と `resets_at`）。https://code.claude.com/docs/en/statusline の「Rate limit usage」。**モデル別の週次（Fable 週次）は含まれない。**Claude Code のセッションが動いているあいだだけ更新される（`refreshInterval` で定期的に更新できる）
  - 2026-10-09 に同じページを読み直し、上の文言が変わっていないことを確かめた。原文: "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, or Max plan credentials on behalf of their users. Moreover, developers may not collect, store, or intermediate Claude.ai credentials or session tokens"
  - **Consumer Terms（Free・Pro・Max に適用。https://www.anthropic.com/legal/consumer-terms 、2025-10-08 発効）§3「Use of our Services」**の禁止事項に、"Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise." がある（2026-10-09 に原文で確認）。このツールは API キーではなくログイン用のトークンで、スクリプトから 120 秒ごとに呼ぶ。`/api/oauth/usage` を外部から呼んでよいという記載は、公式の文書に見当たらない。**公開しなくても、自分で使うだけで、この文言に当てはまる**
  - ステータスライン経由なら、値を取りに行くのは Claude Code 自身で、このツールはスクリプトに渡された値を受け取るだけになる。2026-10-09 に読み直した版でも、`rate_limits` は `five_hour`・`seven_day`（と、Claude apps gateway の `spend_limit`）だけで、モデル別の週次は無い。セッションの最初の API 応答の後に現れる
  - 違反したときの措置（Consumer Terms §12「Termination」、2026-10-09 に原文で確認）: "We may suspend or terminate your access to the Services (including any Subscriptions) at any time without notice to you if we believe that you have breached these Terms"。違反による解約では返金されない。措置には、サービス側で API を止める形（使っている全員が同時に止まる）と、アカウントを止める形（そのアカウントだけ）の 2 通りがあり、どちらを使うかは文書に書かれていない
  - **同じ方式の既存のツール**（2026-10-09、この Mac に入っているもので確認）: VS Code の拡張機能「Claude Usage Meter」（shivakrishnakokkula、0.4.42。説明文は "Unofficial. Session, weekly and per-model Claude usage in the status bar, read from Anthropic's API. Needs a Claude Code OAuth token on the machine"）は、Keychain の `Claude Code-credentials` を `security` で読み、`https://api.anthropic.com/api/oauth/usage` を呼ぶ（`out/core/client.js` 58・299〜324 行目）。Orca（`/Applications/Orca.app` の `app.asar`）も、Keychain のトークンで同じ API を呼ぶ。モデル別の週次はこの API でしか取れないので、表示するツールはこの方式になる。広く使われていることは、Consumer Terms の「明示の許可」には当たらない。利用枠を読むだけのツールが止められたという報告は、2026-10-09 の検索（3 回）では見つからなかった。Anthropic 公式リポジトリの issue #31637（https://github.com/anthropics/claude-code/issues/31637 。この API が 1 つのトークンにつき 5 回ほどで 429 を返すという報告）は、作成の 1 分後にボットが「invalid」を付け、Anthropic の社員の返答が無いまま、放置で閉じられた（2026-06-01）。このツールは User-Agent を変えておらず、Python の既定（`Python-urllib/3.14`）で送る
- **名前の扱い（2026-10-09 に調査）**: リポジトリ名に `claude`、画面の見出しに「Claude Code」を使っている
  - 同じページの「Using the Claude Code name and logo」は、Claude Code を組み込んだ製品について、「Claude Code・Anthropic の名前やロゴを、自分の製品・機能・会社の名前の一部に使えない」「Anthropic が作った・推奨している・提携しているように見せてはならない」と定め、それ以外の名前の使い方は商標のガイドラインによるとしている
  - 商標のガイドライン（https://www.anthropic.com/legal/trademark-guidelines 、2024-08-01 発効）は、リポジトリ名やプロジェクト名についての個別の定めを持たない。全体として「Anthropic が許可した範囲で、事前に承認した資料でのみ使える」「後援・推奨・提携を示すように使ってはならない」と定め、問い合わせ先は marketing@anthropic.com
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
- 公開範囲の変更は `GH_TOKEN=$(security find-generic-password -s gh-token-studioc-co-jp -w) gh repo edit studioc-co-jp/claude-usage-display --visibility public --accept-visibility-change-consequences` で行う（§3 の組織用のトークン）。GitHub の画面から変えてもよい。**2026-10-09 にこのコマンドで public にした**（認証なしで `https://github.com/studioc-co-jp/claude-usage-display` が HTTP 200 を返すことを確認）
- フォント: 画面は macOS に入っているフォント（SF Pro Rounded・ヒラギノ角ゴシック）で描く。リポジトリにはフォントのファイルを含めず、`/System/Library/Fonts/` のパスで参照するだけである。macOS の使用許諾契約（この Mac の `/Library/Documentation/License.lpdf`、日本語版 2 条 E「フォント」）は「Apple ソフトウェアの実行中にコンテンツを表示およびプリントするために、Apple ソフトウェアに含まれるフォントを使用することができます」「当該フォントに付属する埋め込み制限で許可されている場合のみ、コンテンツ内にフォントを埋め込むことができます」と定める。このプログラムは、macOS 上で実行中にこれらのフォントで画面を描き、ディスプレイに表示する。README・記事に載せる画像は描いた結果の画素で、フォントのデータは含まない
