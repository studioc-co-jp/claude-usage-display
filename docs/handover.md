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
- テストは 67 件すべて成功（2026-10-09 時点）（`.venv/bin/python -m unittest discover -s tests`）。5.2 インチの送信部（`turzx_usb.py`）を足した後、自動起動を起動し直し、3.5 インチで 12:00・12:01 の描き直しがエラーなく送られたことをログで確かめた
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
| `claude_usage_display/turzx_usb.py` | 5.2 インチ（TURZX の新しい世代、`1cbe:0050`）への送信。暗号化した 512 バイトの見出し（DES-CBC、鍵 `slv3tuzx`）と PNG（1 MiB を超えると JPEG）を 1 回で書き、応答を確かめる。横向きの画像を縦長に回して送る。実機では未確認 |
| `claude_usage_display/__main__.py` | `preview` / `probe` / `test-pattern` / `run` の 4 コマンド。`run` は常駐ループ |
| `tests/` | 単体テスト 67 件。`fixtures/usage_response.json` は実際の応答から必要な項目だけを残したもの |
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
9. **5.2 インチのディスプレイ**（2026-10-09 にユーザーが注文を決めた。AliExpress 1005010058380485、TURZX 5.2" 1280×720、Option 1-Black、5,538 円、配達予定 10 月 17〜21 日。届くのが再開の条件）。当初は 5 インチ（rev C、1005011742654881）を検討したが、macOS で動かす関門が少ない新しい世代の 5.2 インチに替えた（§4-9）。到着から 90 日以内なら返送料なしで返品できる（§4-9）
   1. **届いたら最初に、Mac で通信できるかを確かめる**（返品の判断はここで決まる）。送信部（`turzx_usb.py`）は 2026-10-09 に先に書いた。見出しのバイト列は phstudy の実装と一致することをテストで固定してある（`tests/test_turzx_usb.py`）
      1. 自動起動を止める（`scripts/uninstall-launch-agent.sh`）。3.5 インチは外す（両方つながっていると 5.2 インチを使うが、確かめる間は 1 台にする）
      2. USB-A のハブにつなぎ、`.venv/bin/python -m claude_usage_display probe`。`1cbe:0050 TURZX 5.2 インチ` と出て、「インターフェースを確保できました」で終われば次へ。別の ID なら、中身の世代が違う個体（§4-9 の #727）。一覧の出力をそのまま記録する
      3. `.venv/bin/python -m claude_usage_display test-pattern`。命令 10（同期）・14（明るさ）・102（PNG）の応答が表示される。先頭が「命令番号 c8 時刻 4 バイト」なら想定どおり。違う形なら、表示された応答を記録し、`turzx_usb.check_response` を実機に合わせて直す（明るさの命令に応答が無いことも考えられる。ライブラリは明るさの応答を確かめていない）
      4. 画面に確認画面が出るか、左上が赤で「左上」か（逆なら `--flip`）、1280×720 と出るかを見る
   2. 通信できたら: `run` で動かす（今は 480×320 の画面を 2.25 倍にして黒地の中央に出す。`__main__.fit_to`）→ 画面の配置を 1280×720 に作り直す → 自動起動で動かす → 別の記事にする（`docs/article-material.md` §12 の 4）
   3. 通信できなかったら: 到着から 90 日以内に返品する（ユーザーが判断する）

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
