# 記事の素材: Claude Code の利用枠を Mac の 3.5 インチディスプレイに出す（2026-10-05 時点）

studioc.co.jp のテックブログ（`/tech`）の記事は、ディスプレイが届いて実機で動いた後に、`~/projects/studioc` で起動したセッションが `/techblog-write` で書きます。この文書は、そのための素材です。2026-10-05 までに行ったことを、出典つきでまとめています。

- 実機で分かったことは、届いた後に §10 に追記します
- 作業の手順や残っている作業は `docs/handover.md` にあります。この文書は「記事に書く話」の側から整理しています
- GitHub のほかのリポジトリを組織へ移す件は、この記事の範囲外なので書いていません

## 1. 一言でいうと

Claude Code の利用枠 3 つ（5 時間・週次・Fable 週次）を、Mac に USB でつないだ 3.5 インチの小さなディスプレイ（Turing Smart Screen）に、メーターで常時表示します。元になった記事のツールは Windows と 9.2 インチ専用だったので、Mac と 3.5 インチで動く版を Python で作り直しました。

完成した画面（見本の値）: `docs/images/gauge.png`

## 2. きっかけ

- nuits_jp（NAKAMURA Atsushi）さんの X の記事「AI専用ダッシュボードの作り方」（https://x.com/nuits_jp/status/2106686059509883050 、2026-10-04）
  - TURZX（Turing Smart Screen）の USB ディスプレイに、Claude Code・Cursor・Codex・Gemini などのトークン消費量や利用枠の残量を常時表示する「Token Dashboard」を紹介しています
  - 材料費は 8,000 円弱と書かれています（記事を紹介する投稿の本文）
  - 専用ディスプレイの利点として、HDMI のサブモニターと違い「ほかのウィンドウを隠さない」「ほかのウィンドウに隠されない」の 2 点を挙げています
  - 画面の送り方は、USB のバルク転送で画像（JPEG・PNG）を流す方式です。先頭 504 バイトを DES-CBC（鍵 `slv3tuzx`）で暗号化した 512 バイトのヘッダーを付けます
- 記事のツール: `nuitsjp/token-dashboard`（https://github.com/nuitsjp/token-dashboard 、MIT、Go）

## 3. 時系列（2026 年）

| 日時 | 出来事 |
|---|---|
| 10-04 | 元の記事が公開される |
| 10-05（16:40 まで） | studioc のセッションで調査と最初の実装（テスト 34 件）。ディスプレイは AliExpress で注文済みで、未着 |
| 10-05 16:40 頃 | このリポジトリのセッションに引き継ぎ。README・CLAUDE.md・自動起動・git を整える |
| 10-05 16:55〜17:06 | 画面を Apple のデザインに寄せる。2 案を作り、ゲージ型を採用。2 回調整 |
| 10-05 17:08 | 自動起動（launchd）を登録。ディスプレイ待ちで常駐を開始 |
| 10-05 17:10〜17:27 | GitHub に push。README に元の記事と経緯を書く。公開の可否に関わる認証の扱いを調べる |
| 10-05 17:54〜18:00 | MIT ライセンス（株式会社studio C）を追加。commit の作成者のメールアドレスを非公開用に書き換える |
| 10-05 18:38〜18:50 | 会社の GitHub 組織 `studioc-co-jp` を作り、ドメインを認証して、リポジトリを移す |

## 4. Mac で動かすまでに調べたこと

### 4-1. 元のツールは Mac では使えない

- `token-dashboard` の `docs/project.md` 12 行目で、「Windows 以外の OS」と「TURZX 9.2インチ以外の機種」を対象外としています。16 行目で、動作環境を Windows 11（x64）と TURZX 9.2 インチ（USB `1CBE:0092`、WinUSB）に限っています
- 配布物は Windows 用のインストーラーだけです（v0.1.6、`token-monitor-turzx-0.1.6-amd64-setup.exe`、2026-10-04）
- 利用枠は、同梱した tokscale で取得します（同 18 行目）

### 4-1-2. メーカーの公式ソフトも Windows 専用（2026-10-07 に調査）

- TURZX の公式サイト（https://www.turzx.com/en/ ）の製品一覧では、8 機種すべての対応 OS が Windows です。3.5 インチは「SYSTEM: Windows 7-11」、ほかの 7 機種は「Windows 10, 11」です
- 3.5 インチ用のソフトの配布ページ（https://www.turzx.com/2025/05/26/35_inch/ 、2026-08-16 更新）にあるのは、「3.5inch app」の英語版と中国語版だけです（いずれも 2025/12/02 版、`.rar`）
- 英語版（`https://down.turzx.com/35inchENG.rar`、約 25.6 MB）の中身は、`UsbMonitor.exe`（2026-06-26 版）、.NET 用の DLL、Windows のドライバー定義（`Driver/usbser/cdc.inf`）でした
- サイト内検索（WordPress の検索 API）で「mac」「macos」「Mac OS」「苹果」を引くと、どれも 0 件でした。macOS 版の配布はありません
- **Mac では、公式ソフトの代わりにこのプログラムが設定します。**明るさ（`SET_BRIGHTNESS`、110）と向き（`SET_ORIENTATION`、121）は、rev A の命令でパネルに直接送れます（§4-4）。`run` と `test-pattern` は、接続のたびに `--brightness`（既定 30）と `--flip` の値を送ります（`claude_usage_display/turing.py` の `TuringRevA.initialize`）。公式ソフトの「Theme」は画面の絵柄の選択なので、自前で描くこのプログラムでは使いません

### 4-2. 機種と、見分け方の落とし穴

- 選んだのは Turing Smart Screen 3.5 インチ rev A（480×320、USB `1a86:5722`、シリアル番号 `USB35INCHIPSV2`）です。AliExpress の TURZX の商品（商品 ID 1005008850981488）で、商品画像の付属ソフトの画面（ウィンドウ名 `Turing Smart Screen`）が rev A の付属ソフトと一致していました（studioc のセッションが調べた結果。`docs/handover.md` §2）
- **落とし穴: 同じ 3.5 インチでも、XuanFang の rev B は USB の ID が同じ `1a86:5722` です。**違うのはシリアル番号（`2017-2-25`）だけで、通信方式は違います（10 バイト単位のコマンド）。出典は turing-smart-screen-python の `library/lcd/lcd_comm_rev_a.py` 72・74 行目と、`lcd_comm_rev_b.py` 75・77 行目です
- ほかの機種: Turing の 2.1・2.8・5・8 インチは rev C（`lcd_comm_rev_c.py` 127 行目）、Kipye の 3.5 インチは rev D（USB `454d:4e41`。`lcd_comm_rev_d.py` 43・59 行目）
- macOS 27 では `system_profiler SPUSBDataType` が無くなり、`SPUSBHostDataType` を使います（`system_profiler -listDataTypes` で確認）。出力は `Serial Number` → `USB Vendor ID` → `USB Product ID` の順です

### 4-3. macOS ではシリアル経由だと画像が崩れる（この記事のいちばんの山場）

- 3.5 インチの定番のライブラリ `mathoudebine/turing-smart-screen-python`（GPL-3.0-or-later）は、README の対応 OS のバッジで、macOS に「⚠️major bug」の注記を付けています（README 11 行目）。issue #7「Screen displays corrupted images on Mac」は 2022-02-02 から open のままです
- 原因は、issue #7 のコメント（amarok30、2026-08-21。Mac mini M4・macOS 26.5.2・`1a86:5722`・`USB35INCHIPSV2` で検証）で示されました
  - パネルのファームウェアは、USB の転送の単位で動きます。転送の先頭をコマンドとして読み、その転送の残りは捨てます
  - 画像の表示コマンド（`DISPLAY_BITMAP`）の後は、幅×高さ×2 バイトの画素を数え終えるまで、届いたものをすべて画素として扱います
  - macOS の CDC ドライバー（シリアルポートの裏側）は、書き込みを任意に分割・結合して転送します。そのため、コマンドが画素の中に混ざります。一度ずれると、電源を入れ直すまで崩れ続けます
- 回避策（同じコメントと、その実装の gist https://gist.github.com/amarok30/cddaa9a9818d6830a74d9332f501047e ）: シリアルポートを使わず、libusb でバルク OUT エンドポイント `0x03`（インターフェース 1）に直接書きます。守ることは 4 つです
  1. コマンドは 1 つずつ、それだけで 1 回の転送にする
  2. 向きの設定（`SET_ORIENTATION`）は 11 バイトにする
  3. 画素は 64 バイトの倍数で区切り、合計をちょうど 幅×高さ×2 バイトにする
  4. 画素を送っている途中に、ほかのものを書かない
- **GPL のコードは持ち込んでいません。**ライブラリも gist も GPL-3.0-or-later（各ファイルの `SPDX-License-Identifier`）です。使ったのは仕様（コマンド番号・バイトの並び・転送の規則）だけで、送信部の `claude_usage_display/turing.py` は自前で書きました
- 同期が崩れたまま起動したときの備えとして、接続のたびに全画面分の黒を送り、数え残しを埋めてから描き始めます（`TuringRevA.resync`）

### 4-4. rev A の通信仕様（`lcd_comm_rev_a.py` から）

- コマンド番号: RESET 101、CLEAR 102、SCREEN_OFF 108、SCREEN_ON 109、SET_BRIGHTNESS 110、SET_ORIENTATION 121、DISPLAY_BITMAP 197
- 6 バイトの形式: x・y・ex・ey を 10 ビットずつ詰め、最後の 1 バイトがコマンド番号
- 向き: 縦 0、縦（逆）1、横 2、横（逆）3（送る値は +100）
- 明るさ: 0 が最も明るく、255 が最も暗い
- 画素: RGB565 のリトルエンディアン。Pillow の組み込みの変換は RGB からは使えないため、手で計算しています

### 4-4-2. 明るさと向きを、命令で直接設定する（記事に載せる詳細）

メーカーが用意している設定の手段は、Windows 専用の公式ソフトだけです（§4-1-2）。ただ、明るさや向きの設定も、公式ソフトがパネルへ送っている命令にすぎません。同じ命令を送れば、Mac からでも設定できます。

**命令の形（rev A）**: 6 バイトです。先頭 5 バイトに、4 つの数 x・y・ex・ey を 10 ビットずつ詰め、最後の 1 バイトに命令番号を置きます（`lcd_comm_rev_a.py` の `SendCommand`、79〜86 行目）。

| バイト | 中身 |
|---|---|
| 0 | x の上位 8 ビット（`x >> 2`） |
| 1 | x の下位 2 ビットと、y の上位 6 ビット |
| 2 | y の下位 4 ビットと、ex の上位 4 ビット |
| 3 | ex の下位 6 ビットと、ey の上位 2 ビット |
| 4 | ey の下位 8 ビット |
| 5 | 命令番号 |

**命令番号**（同ファイル 32〜40 行目）: RESET 101、CLEAR 102、SCREEN_OFF 108、SCREEN_ON 109、SET_BRIGHTNESS 110、SET_ORIENTATION 121、DISPLAY_BITMAP 197。同じ一覧の後半（HELLO 69、SET_MIRROR 122 など）は、注記に「次の世代の機種だけが対応」とあり、rev A では使いません。

**明るさ（SET_BRIGHTNESS、110）**
- 明るさの値を x に入れて送ります。パネルの値は 0 が最も明るく、255 が最も暗い、という逆向きです（同ファイル 146〜154 行目のコメント「0 being the brightest and 255 being the darkest」）
- 割合（0〜100%）からの換算は `255 - 割合 × 255 / 100` です（このプログラムの `turing.py` の `brightness_level`）
- 実際に送るバイト列（このプログラムで生成して確認。2026-10-07）

  | 明るさ | パネルの値 | 送るバイト列 |
  |---|---|---|
  | 100% | 0 | `00 00 00 00 00 6E` |
  | 30%（既定） | 178 | `2C 80 00 00 00 6E` |
  | 0% | 255 | `3F C0 00 00 00 6E` |

  30% の例: 178 は 2 進数で `10110010`。上位 8 ビット `101100` を 0 バイト目に入れて `0x2C`、下位 2 ビット `10` を 1 バイト目の先頭に入れて `0x80` になります

**向き（SET_ORIENTATION、121）**
- 6 バイトの命令に、向き（縦 0・縦の逆 1・横 2・横の逆 3 に 100 を足した値）、幅（2 バイト）、高さ（2 バイト）を続けた 11 バイトです（同ファイル 156〜176 行目）
- 横向き（480×320）: `00 00 00 00 00 79 66 01 E0 01 40`
- 横向きの上下逆（`--flip`）: `00 00 00 00 00 79 67 01 E0 01 40`
- **macOS での注意**: 元のライブラリは、この命令を 16 バイトの入れ物（後ろ 5 バイトは 0）で送っています（同 164 行目の `bytearray(16)`）。macOS で崩れない送り方では、ちょうど 11 バイトにします（issue #7 で示された回避策。§4-3）

**送り方**
- 命令は 1 つずつ、それだけで 1 回の USB 転送にして、バルク OUT エンドポイント `0x03` に書きます（§4-3）
- このプログラムは、ディスプレイに接続するたびに「全画面分の黒で同期を取り直す → 向き → 明るさ」の順に送ります（`turing.py` の `TuringRevA.initialize`、174〜177 行目）。パネル側に設定が残っていなくても、つなぎ直せば毎回同じ状態になります
- 使い方: `--brightness N`（0〜100、既定 30）と `--flip`。自動起動では `scripts/install-launch-agent.sh --brightness 40 --flip` のように登録し直します
- 公式ソフトにある「Theme」（画面の絵柄の選択）は、画面を自前で描くこのプログラムには要りません

### 4-5. 利用枠の取り方

- Claude Code が macOS の Keychain に保存したログイン情報（項目名 `Claude Code-credentials`）からアクセストークンを読み、`GET https://api.anthropic.com/api/oauth/usage`（ヘッダー `anthropic-beta: oauth-2025-04-20`）を呼びます。呼び方は tokscale（`junhoyeo/tokscale`、MIT）の `crates/tokscale-cli/src/commands/usage/claude.rs` と同じです
- 応答の `limits` 配列に、5 時間（`kind: "session"`）・週次（`weekly_all`）・モデル別の週次（`weekly_scoped`、`scope.model.display_name: "Fable"`）が入っています
- **ログイン情報は読むだけで、書き戻しません。**tokscale には、期限切れのトークンを更新してログイン情報に書き戻した結果、Claude Code のログインが切れる不具合がありました（tokscale #1001「Claude usage refresh corrupts Claude Code credentials and logs users out」、修正済み）。期限切れのときは「ログイン切れ（Claude Code を起動すると戻ります）」と表示し、更新は Claude Code に任せます
- 応答のトップレベルには、用途の分からない項目が多数あります。社内のコード名に見える名前が並ぶため、テストの fixture にも記事にも載せません

## 5. 作ったものの仕組み

1. 2 分ごとに Keychain からトークンを読み、利用枠を取得します
2. 毎分（分が変わった直後）、Pillow で 480×320 の画像を描き、RGB565 の 307,200 バイトに変換します。残り時間の表示を進めるため、取得とは別に描き直します
3. 前回送ったものと同じなら送りません。違えば、表示コマンド（6 バイト）を 1 回の転送で送り、続けて画素を 4,096 バイトずつ送ります
4. ディスプレイがつながっていないあいだは、10 秒ごとに接続を確かめるだけで、API は呼びません

- コマンドは 4 つ: `preview`（画像だけ作る。`--demo` で見本の値）、`probe`（USB の情報と、インターフェースを確保できるか）、`test-pattern`（向きと色の確認画面）、`run`（常駐）
- 描画と変換は 1 回 38 ミリ秒（2026-10-05 にこの Mac で計測）
- 単体テスト 49 件
- ディスプレイが届く前でも、送信データ（RGB565）を画像に戻せば、パネルに映る画素とまったく同じ画像を確かめられます。デザインはこの方法で詰めました

## 6. 画面のデザインの変遷

### 6-1. 最初の画面（横棒）

`docs/images/classic.png`。メーター 3 本を縦に並べ、使用率とリセット時刻を出します。いまも `--theme classic` で使えます。

### 6-2. 「もう少しおしゃれに、Apple のデザインパターンを参考に」

ユーザーの依頼は「全体的にいい感じだが、もう少しおしゃれに。元に戻す可能性がある前提で、Apple のデザインパターンを参考に」でした。そこで 2 案を作りました。

- A: 設定アプリのグループ化リスト風（`docs/images/design-a-list.png`）
- B: ウィジェットのバッテリー風の円形ゲージ（`docs/images/design-b-before-centering.png`）

**B を採用**しました。「元に戻す前提」に合わせて、横棒の画面はコードに残し、`--theme` で切り替えられるようにしています。

### 6-3. Apple の作りから取り入れたもの（出典つき）

- **色**: Human Interface Guidelines（HIG）の Color の、ダークモードのシステムカラー（https://developer.apple.com/design/human-interface-guidelines/color 。2025-06-09 に値が更新された版）

  | 用途 | HIG の名前 | 値（ダーク） |
  |---|---|---|
  | 通常（70% 未満） | Blue | 0, 145, 255 |
  | 注意（70% 以上） | Orange | 255, 146, 48 |
  | 危険（90% 以上） | Red | 255, 66, 69 |
  | 補足の文字 | Gray | 142, 142, 147 |
  | 控えめな文字 | Gray (2) | 99, 99, 102 |

- **文字の大きさ**: HIG の Typography（https://developer.apple.com/design/human-interface-guidelines/typography ）の、iOS の既定（Large）の文字スタイルの pt を、そのままピクセルで使いました（Title 1 28・Subhead 15・Footnote 13・Caption 1 12）
  - 根拠: iPhone 3GS の技術仕様（https://support.apple.com/kb/SP565 ）に「3.5-inch (diagonal) … 480-by-320-pixel resolution at 163 ppi」とあります。このパネルも 3.5 インチ・480×320（計算で約 165 ppi）で、初期の iPhone と同じ大きさと解像度です。iOS の文字の大きさをそのまま当てれば、iPhone で見る文字とほぼ同じ物理的な大きさになります
- **字形**: 数字は SF Pro Rounded（`/System/Library/Fonts/SFNSRounded.ttf`。太さの軸を持つ可変フォントで、Pillow の `set_variation_by_name("Semibold")` で太さを選ぶ）、日本語はヒラギノ角ゴシックです。「%」は小さく灰色にしています
- **時刻**: iOS の日本語表記にならい、時の先頭に 0 を付けません（「9:55」）
- **値が無いとき**: ヘルスケアや天気と同じく「--」で表し、ゲージの軌道を灰色にします
- **縁の滑らかさ**: 図形は 4 倍の大きさで描いてから縮め（LANCZOS）、文字は縮めた後に等倍で書きます。文字まで縮めると、かすれるためです

### 6-4. ハマりどころ: RGB565 では灰色が緑に寄る

送信データを画像に戻して確かめたところ、カードの面が緑がかっていました。RGB565 は赤・青が 5 ビット、緑が 6 ビットなので、HIG の Gray (6)（28, 28, 30）は（24, 28, 24）に落ちます。RGB565 でそのまま表せる無彩色のうち、液晶で黒地との差が見えやすい明るい側の（33, 32, 33）に置き換え、テストで固定しました（`tests/test_gauge.py` の `test_card_color_survives_rgb565`）。

### 6-5. 仕上げの調整（ユーザーの指示 2 回）

1. 「3 つ並んだカード内の要素が上に寄っている → 縦方向に中央寄せ」: 中身の高さを、フォントの実寸（見出しの字の上端から、残り時間の字の下端まで）で求め、カードの中央に置く計算にしました
2. 「一番下の『あと◯時間』をもう少し上の要素と離して、そのうえで全体を中央に」: 行間を 20 ピクセルから 27 ピクセルに広げました。中身の高さ 208 ピクセルに対して、上下の余白がどちらも 32 ピクセルになります

完成形: `docs/images/gauge.png`

## 7. 自動起動（launchd）で分かったこと（macOS 27.0.1）

- ログイン時に `run` を起動し、落ちたら起動し直す LaunchAgent を作りました（`launchd/` のひな形と `scripts/` の登録・解除のスクリプト）。launchd は `~` を展開しないので、登録のスクリプトがひな形のパスを絶対パスに置き換えて配置します
- launchd は `LANG`・`LC_ALL` を渡しません。それでも Python 3.14 は、C ロケールで UTF-8 モードに自動で入ります（launchd 経由で `sys.flags.utf8_mode = 1` を確認）。念のため、plist で `PYTHONUTF8=1` を明示しています
- launchd から `security find-generic-password` で Keychain を読んでも、確認の画面は出ず、利用枠の取得まで通りました
- **`launchctl bootout` は、サービスの終了を待たずに戻ります。**直後の `launchctl print` では、まだ読み込まれたままで、プロセスも残っていました。登録・解除のスクリプトは、消えるまで待ってから次へ進みます
- `KeepAlive` が true なので、`kill -9` で落としても約 3 秒で起動し直しました
- 登録前にオプションの誤りを止めます。誤ったまま登録すると、launchd が 10 秒ごとに起動し直し続けるためです（本物の引数解析を通し、起動だけを差し替えて確かめる）

## 8. 途中で見つけて直した不具合

- `--brightness 150` のような範囲外の値が起動時に止まらず、ディスプレイをつないだ時点で初期化の失敗を 10 秒ごとに繰り返す作りでした → 引数の解析で止める
- 取得に失敗したときの最も長い文言「ログイン切れ（Claude Code を起動すると戻ります）」が、時刻と合わせて 482 ピクセルになり、使える幅 448 ピクセルを超えて右端で切れていました → 理由と時刻を左右に分け、収まらないときは文字を縮める
- 最初の取得に失敗したとき、`--model` の指定に関係なく、見出しが「Fable週次」になっていました → メーターの名前を 1 か所で決める

## 9. 公開に向けて決めたこと・調べたこと

### 9-1. ライセンス

MIT。著作権者は株式会社studio C です。本文は、GitHub の Licenses API の `mit` から作りました。

### 9-2. commit の作成者のメールアドレスを公開しない

- 個人のメールアドレスが commit の作成者欄に入っていたため、GitHub の非公開用アドレス（`ID+ユーザー名@users.noreply.github.com`）に書き換えました。形式の出典は GitHub の文書「Email addresses reference」です
- 手順: `git filter-repo --mailmap` で作成者欄を、`--replace-text` で文書の中に書いていたアドレスを、履歴から消しました。日時とファイルの中身は変わりません
- **強制 push では足りません。**GitHub の文書「Removing sensitive data from a repository」に、書き換えて強制 push しても、古い commit は SHA-1 を指定すれば GitHub のキャッシュから見られると書かれています。また、GitHub Support は機微でないデータの削除には応じません。そのため、GitHub 上のリポジトリを削除して作り直し、書き換えた履歴を push しました。作り直した後は、古い commit を取り出せないこと（`not our ref`）を確かめています
- 「Block command line pushes that expose my email」は使っていません。この設定は push のたびに最新の commit を調べるため、個人のアドレスで commit しているほかのリポジトリの push まで止まります

### 9-3. 置き場所

会社の GitHub 組織 `studioc-co-jp`（表示名 studio C、Free プラン）に置きました（`studioc-co-jp/claude-usage-display`、2026-10-05 時点で private）。記事には、この組織の URL を載せます。

### 9-4. 認証の扱い（未決。記事を書く前に決める）

- このツールは、Claude Code のログイン用のトークン（OAuth）を読み、公式には説明されていない API を呼んでいます
- Claude Code の「Legal and compliance」（https://code.claude.com/docs/en/legal-and-compliance 、「Authentication and credential use」）の定め
  - OAuth の認証は、サブスクリプションの購入者が Claude Code と Anthropic 純正のアプリを普通に使うためのもの
  - 製品やサービスを作る開発者は API キーを使う。開発者は Claude.ai の資格情報やセッショントークンを、収集・保存・仲介してはならない
  - Anthropic は、これらの制限を予告なく執行できる
- このツールは、本人の Mac で本人のトークンを読むだけで、保存も他人への提供もしません。ただ、純正ではないアプリがこのトークンを使うことを、上の文書は許可も禁止もしていません
- 公式に値を受け取れる経路: ステータスラインのスクリプトに渡る JSON の `rate_limits.five_hour` / `rate_limits.seven_day`（使用率とリセット時刻。https://code.claude.com/docs/en/statusline の「Rate limit usage」）。ただし、次の制約があります
  - モデル別の週次（Fable 週次）は含まれません
  - Claude Code が動いているあいだだけ更新されます（`refreshInterval` で定期的に更新はできる）
  - この Mac では、ステータスラインの枠をすでに別のツール（Orca の `~/.orca/agent-hooks/claude-statusline.sh`）が使っています。Claude Code に設定できるステータスラインのコマンドは 1 つだけです
- 選択肢: 公開版はステータスライン経由にする／今の方式のまま公開する／Anthropic に問い合わせる（上記ページが sales への問い合わせを案内している）／リポジトリは private のままにする

## 10. 実機で分かったこと（ディスプレイが届いたら追記する）

ディスプレイは 2026-10-05 時点で未着です。届いたら `docs/handover.md` §5-6 の順に確かめ、結果をここに書きます。記事に要るのは次の項目です。

- インターフェース 1 を確保できたか（macOS の CDC ドライバーとの取り合い）
- 向き（`--flip` が要ったか）と、色（赤と青が入れ替わっていないか）
- 明るさの見え方（既定は 30）
- 電源を入れ直したとき、明るさと向きがパネルに残るか（残らなくても、このプログラムは接続のたびに送るので表示には困らない。記事で「公式ソフトで一度設定すれば残るのか」に答えるため）
- 1 画面の転送にかかる時間
- ゲージ型の見え方（リングの縁、灰色の文字の読みやすさ、カードの面と黒地の差）
- 実際にディスプレイに映った写真（記事用）

## 11. 記事にするときの注意

- 実際の利用枠が写った画像は載せません。画面の画像は `preview --demo`（見本の値）で作ります
- 応答のトップレベルにある用途不明の項目（社内コード名に見える名前）には触れません
- アクセストークンの値や、個人のメールアドレスを載せません
- GPL のコードを流用していないことと、仕様をどこから得たか（issue #7、gist、`lcd_comm_rev_a.py`）を書きます
- 元の記事と Token Dashboard への着想の謝辞とリンクを載せます
- 認証の扱い（§9-4）を決めてから書きます

## 12. 記事に必ず入れること（ユーザーの指示。2026-10-07）

1. **メーカーの公式ソフトは Windows 専用で、macOS 版は配布されていないこと**（§4-1-2。製品一覧の対応 OS、3.5 インチの配布ページ、配布物の中身、サイト内検索の結果）
2. **明るさなどの設定は、メーカーが用意した手段では公式ソフトからしかできないが、パネルへ命令を直接送れば Mac からでも設定できること。その詳細**（§4-4-2。命令の形、明るさと向きの命令番号と値の換算、実際のバイト列、macOS での送り方の注意、このプログラムでの使い方）
