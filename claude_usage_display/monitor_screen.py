"""サーバーの状態の画面（monitor コマンド、3.5 インチ。横置き 480×320・縦置き 320×480）。

2×2 に、リングと数字を並べる。見出しに、外形・死活監視の判定を出す。

- リングの色は、いちばん新しい値で変わる。しきい値の 15 ポイント手前からオレンジ、しきい値以上で赤
- サイト・サーバーの異常（``server_monitor.assess`` の ``alerts``。値はしきい値以上が ``datapoints`` 回続いたとき）が
  あれば、画面全体を明るい赤
  （HIG の Red）にする。赤い地では赤の文字が見えないため、アラートの項目を白ではっきり、ほかを薄く出す
- ジョブの障害などは、地を黒のまま、見出しにオレンジで件数を出す
- 横置きは、区画の左にリング、リングの中に数字、右に名前としきい値。縦置きは、名前の下にリング、リングの中に数字
  （どちらもユーザーが見本の画像で選んだ。縦置きは 2026-10-10・2026-10-11、横置きは 2026-10-15。横置きは
  それまで、リングの右に名前と大きな数字を出していた）
- 設定に ``logo`` があれば、見出しの名前の左にロゴを出す。大きさと縦の位置は、利用枠の画面の 3.5 インチの
  アイコンと同じ（20 ピクセル角の枠。名前の字の高さの中ほど）。地は黒と赤になるので、ロゴは白一色にする
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache

from PIL import Image, ImageDraw

from .gauge import (BACKGROUND, BLUE, CARD, DARK_TRACK_MIX, ICON_GAP, ICON_SIZE, LABEL, ORANGE, RED, SECONDARY, _mix,
                    load_mark, paste_mark, rounded)
from .render import JST, SMALL_WEIGHT, fit_font, font
from .server_monitor import Assessment, MonitorConfig, ServerStatus, warning_tint

SCALE = 4
GREEN = (48, 209, 88)  # HIG の Green（ダーク）
WHITE = (255, 255, 255)
LOGO_RISE = 5.5  # ロゴの縦の中心を、名前の基準線からこれだけ上げる（利用枠の画面の見出しのアイコンと同じ）
TITLE_GAP = 8  # 名前と、右の時刻・同じ行の監視の状態との間
# 下の行が 2 行以上のときの行の間隔（この Mac の状態の画面の CPU の「性能」「効率」。1 行目はしきい値と同じ位置。
# 2026-10-15、名前の高さをサーバーの画面とそろえる案をユーザーが選んだ）
DETAIL_LINE = 18


@dataclass(frozen=True)
class _CounterRows:
    """件数の行。左に名前、中ほどに 1 時間ごとの棒グラフ、右に直近 24 時間の件数。寸法は 3.5 インチの値。"""

    top: float                              # 1 行目の上端
    height: float                           # 行の高さ
    left: float
    right: float
    baseline: float                         # 行の上端から、名前と件数の基準線まで
    spark: tuple[float, float, float, float]  # 棒グラフの左端・幅・高さ・下端（行の上端から）
    label_size: int
    number_size: int
    unit_size: int


@dataclass(frozen=True)
class _Layout:
    """配置。座標はすべて 3.5 インチの画面のピクセル。区画の中の位置は区画の左上から測る。

    ``k`` は、描くときに座標と字の大きさに掛ける倍率（5.2 インチは高さの比 720 ÷ 320 = 2.25）。
    ``headings`` は灰色の小見出し（x・y・文言・大きさ・太さ・anchor）、``counter_rows`` は件数の行（無ければ描かない）。
    """

    size: tuple[float, float]
    inset: int                                   # 見出しの左右の余白
    title_baseline: float                        # 名前と時刻の行
    pill: tuple[int, int, int, int]              # 赤の状態でアラートを出す白い帯
    status_baseline: float                       # 監視の状態の文言の行（帯の中の文字もこの行）
    dot_y: float                                 # 監視の状態の点の中心
    status_size: int                             # 監視の状態の文言の大きさ
    alert_size: int                              # 帯の中のアラートの大きさ
    dot_radius: float                            # 監視の状態の点の半径
    stamp_size: int                              # 右上の取得の時刻の大きさ
    # アラートが 2 件以上のとき、帯を 2 行にする場合の帯と各行の位置（None なら 1 行に「ほか N 件」まで詰める）
    tall_pill: tuple[int, int, int, int] | None
    tall_baselines: tuple[float, float] | None
    cells: tuple[tuple[int, int], ...]           # 2×2 の各区画の左上
    ring: tuple[float, float, float, float]      # 中心 x・中心 y・半径・太さ
    label: tuple[float, float, str, int]         # 名前の位置・anchor・大きさ
    number: tuple[float, float, int, int, bool]  # 数字の位置・大きさ・% の大きさ（0 なら出さない）・中央にそろえるか
    threshold: tuple[float, float, str, int]     # しきい値の位置・anchor・大きさ
    dividers: tuple[tuple[float, float, float, float], ...]
    k: float = 1.0
    headings: tuple[tuple[float, float, str, int, int, str], ...] = ()
    counter_rows: _CounterRows | None = None


LANDSCAPE = _Layout(
    # 監視の状態・帯の中のアラート・右上の時刻を、実機を見たユーザーの指示で縦置きと同じ大きさにした（2026-10-15。
    # 文言 13→18・点の半径 4.5→6・アラート 15→18・時刻 13→16。帯は 6〜32 → 4〜34）。見出しは 1 行のまま
    # （ユーザーが見本で選んだ）。帯の幅は変えていないので、長いアラートは帯に合わせて縮む。
    # 時刻（「00:00 更新」の幅 84）の左端は 376 で、帯の右端（364）との間は 12 ピクセル
    size=(480, 320), inset=20, title_baseline=25, pill=(116, 4, 364, 34), status_baseline=25, dot_y=18.5,
    status_size=18, alert_size=18, dot_radius=6, stamp_size=16, tall_pill=None, tall_baselines=None,
    # 数字をリングの中に入れ、名前としきい値をリングの右で縦の中ほどに置く（2026-10-15、ユーザーが見本で選んだ）。
    # 名前は、実機を見たユーザーの指示で 18→22 にした（2026-10-27、見本で選んだ）。
    # 続けて、ユーザーの指示「視認性を上げる」で、しきい値（下の行）を 14→15 にし、リングの中の % を外して
    # 数字を 30→38 にした（同日、見本で選んだ案 B）。しきい値を名前と同じ白にもしたが、実機を見たユーザーが
    # 「がちゃがちゃする」として灰色に戻した。15 ピクセルの下の行を区切り線の手前に収めるため、名前と下の行を
    # 126→119 へ寄せた（リングの外側 110 との間は 9）。左の列の「しきい値 80%」（15 ピクセルで幅 99）の右端は 238 で、
    # 区切り線（240）の 2 ピクセル手前。しきい値は 2 桁の整数まで収まる。「ディスク」（22 ピクセルで幅 87）の
    # 右端は 226。数字の「100」（幅 71）はリングの内側（直径 82）に収まる。
    # 2026-11-03、ユーザーの指示「3.5 モニターの罫線は消してその分項目を大きくして」で、縦横の罫線を消し、名前を
    # 22→24・数字を 38→40 にした。リングは横幅で大きさが決まる（左の列のしきい値の右端 238 と、右の列のリングの
    # 左端 256 の間は 18）ので変えていない。「ディスク」（24 ピクセルで幅 95）の右端は 234、「100」（40 で幅 75）は
    # リングの内側（82）に収まる
    cells=((20, 44), (250, 44), (20, 182), (250, 182)), ring=(58, 69, 52, 11), label=(119, 65, "ls", 24),
    number=(58, 84, 40, 0, True), threshold=(119, 90, "ls", 15), dividers=())
PORTRAIT = _Layout(
    size=(320, 480), inset=16, title_baseline=26, pill=(16, 38, 304, 70), status_baseline=60, dot_y=53.5,
    # 監視の状態は、実機を見たユーザーの指示で大きくした（2026-10-11。文言 13→18、帯の中 15→18）。
    # 1 行に「ほか N 件」まで詰めると 12 ピクセルまで縮むので、アラートが 2 件以上なら帯を 2 行にする
    status_size=18, alert_size=18, dot_radius=6, tall_pill=(16, 35, 304, 87), tall_baselines=(57, 79),
    stamp_size=16,  # 右上の時刻も、実機を見たユーザーの指示で大きくした（2026-10-11。13→16）
    # 名前・しきい値・リングは、実機を見たユーザーの指示で大きくした（2026-10-11。名前 15→18、しきい値 12→14、
    # リングの半径 46→56・太さ 10→12、数字 30→34）
    cells=((0, 80), (160, 80), (0, 280), (160, 280)), ring=(80, 100, 56, 12), label=(80, 28, "ms", 18),
    number=(80, 112, 34, 16, True), threshold=(80, 184, "ms", 14), dividers=((160, 92, 160, 466), (16, 280, 304, 280)))

# 5.2 インチ（1280×720）。高さの比 2.25 倍で描く（2026-11-03。docs/handover.md §4-25・§4-26）。
# 見出しは横置きと同じ（帯は同じ幅 248 で中央）。その下を Apple の HIG の「関係する項目をまとめる」「重要なものを
# 上と左に」（Layout）と、グループ化した一覧（Lists and tables）にならって 2 つにまとめた。上の「サーバー」は
# 4 つのリングを横 1 列に、下の「サイト」は件数の行（5xx・PHP エラー）を、左に名前・中ほどに直近 24 時間の
# 1 時間ごとの棒グラフ・右に件数で出す。ユーザーが見本で選んだ（それまでの 2×2 は §4-25）。寸法は 5.2 インチの
# 見本のピクセルで書き、_px で 3.5 インチの寸法にする
_K_LARGE = 720 / 320
_W_LARGE = 1280 / _K_LARGE


def _px(value: float) -> float:
    """5.2 インチの画面のピクセルを、3.5 インチの寸法にする。"""
    return value / _K_LARGE


LANDSCAPE_LARGE = replace(
    LANDSCAPE, size=(_W_LARGE, 320), k=_K_LARGE, pill=(round(_W_LARGE / 2 - 124), 4, round(_W_LARGE / 2 + 124), 34),
    # 「サイト」の小見出しを消し、「直近 24 時間」を左端にそろえ、縦の間を詰めた分でリングを外径 172→200 px・
    # 数字 61→70 px にした（同日、ユーザーの指示）
    cells=tuple((_px(190 + 300 * i), 0) for i in range(4)),  # リングの中心の x（区画は幅 300 px で 4 つ）
    # 下のまとまりを下へ寄せて画面の下の余白を減らし（同日、ユーザーの指示）、続けて上下のまとまりの間の罫線を消して、
    # その分リングを外径 200→228 px・数字 70→81 px にした（同日、ユーザーの指示）。リングの上端は「サーバー」の
    # 小見出しから 13 px、しきい値の字と「直近 24 時間」の字の間は約 35 px
    # 続けて「サーバー」の小見出しを消し、リングの上端を 140→128 px（異常の 2 行の帯の下端 121.5 px の下）に上げて、
    # 外径 228→240 px・数字 81→86 px にした（同日、ユーザーの指示）。名前・しきい値の位置は変えていない
    ring=(0, _px(248), _px(120), _px(26)), label=(0, _px(408), "ms", 14), number=(0, _px(278), 38, 0, True),
    threshold=(0, _px(438), "ms", 11), dividers=(),
    headings=((_px(60), _px(498), "直近 24 時間（1 時間ごと）", 10, SMALL_WEIGHT, "ls"),),
    counter_rows=_CounterRows(top=_px(504), height=_px(108), left=_px(60), right=_px(1220), baseline=_px(68),
                              spark=(_px(330), _px(560), _px(52), _px(76)), label_size=15, number_size=22,
                              unit_size=12))


def layout_for(size: tuple[int, int], portrait: bool = False) -> _Layout:
    """ディスプレイの大きさ（ピクセル）に合う配置。1280×720 は 5.2 インチの横置き、それ以外は 3.5 インチ。"""
    if tuple(size) == (1280, 720):
        return LANDSCAPE_LARGE
    return PORTRAIT if portrait else LANDSCAPE


class _Shapes:
    """図形の下書き。座標は 3.5 インチの寸法で受け取り、``k`` 倍の画面に描く。"""

    def __init__(self, size, background, k: float = 1.0):
        # 大きい画面は、拡大して描く倍率を下げ、描く大きさを 3.5 インチと同じくらいにする（gauge と同じ）
        supersample = SCALE if k == 1 else max(2, round(SCALE / k))
        self.factor = SCALE if k == 1 else k * supersample
        self.size = (round(size[0] * k), round(size[1] * k))
        self.image = Image.new("RGB", (self.size[0] * supersample, self.size[1] * supersample), background)
        self.draw = ImageDraw.Draw(self.image)

    def _box(self, x0, y0, x1, y1):
        return x0 * self.factor, y0 * self.factor, x1 * self.factor, y1 * self.factor

    def circle(self, cx, cy, r, fill):
        self.draw.ellipse(self._box(cx - r, cy - r, cx + r, cy + r), fill=fill)

    def pill(self, box, fill, radius: float | None = None):
        radius = (box[3] - box[1]) / 2 if radius is None else radius
        self.draw.rounded_rectangle(self._box(*box), radius * self.factor, fill=fill)

    def ring(self, cx, cy, radius, ring_width, percent: float | None, color, track):
        box = self._box(cx - radius, cy - radius, cx + radius, cy + radius)
        width = round(ring_width * self.factor)
        self.draw.ellipse(box, outline=track, width=width)
        if percent is None or percent <= 0:
            return
        sweep = 360 * min(percent, 100) / 100
        self.draw.arc(box, -90, -90 + sweep, fill=color, width=width)
        middle = radius - ring_width / 2
        for angle in (-90, -90 + sweep):
            a = math.radians(angle)
            self.circle(cx + middle * math.cos(a), cy + middle * math.sin(a), ring_width / 2, color)

    def finish(self) -> Image.Image:
        return self.image.resize(self.size, Image.LANCZOS)


@lru_cache(maxsize=4)
def _logo(path: str) -> Image.Image:
    return load_mark(path)


BIG_SIZE = 24   # 見出しの名前を出さない設定のとき、異常の文言の大きさ（1 行）
BIG_SMALL = 21  # 1 行に収まらないとき、2 行にして使う大きさ（収まらなければ BIG_MIN まで下げる）
BIG_MIN = 17


def _scaled(size: int, k: float) -> int:
    """3.5 インチの字の大きさを、``k`` 倍の画面の大きさにする。"""
    return size if k == 1 else round(size * k)


def _big_lines(text: str, width: float, weight: int, k: float = 1.0):
    """異常の文言を、1 行（BIG_SIZE）か、収まらなければ 2 行（BIG_SMALL → BIG_MIN）にする。

    2 行にするときは、区切りのよい位置（「名前: 理由」・「…　ほか N 件」・「件数（名前 ほか）」）を、この順に探し、
    見つかった位置で収まる最も大きい大きさを使う。区切りが無ければ、1 行のまま収まる最も大きい大きさ（BIG_SMALL →
    BIG_MIN）を使う。それでも収まらなければ、字数で折り返し、2 行目は「…」で切る。
    ``width`` は画面のピクセル、大きさは 3.5 インチの値を ``k`` 倍して使う。
    """
    big = font(_scaled(BIG_SIZE, k), weight)
    if big.getlength(text) <= width:
        return [text], big
    for sep, tail in ((": ", ""), ("　ほか", "ほか"), ("（", "")):
        head, found, rest = text.partition(sep)
        if not found:
            continue
        parts = [head, (tail + rest).removesuffix("）")]
        for size in range(BIG_SMALL, BIG_MIN - 1, -1):
            small = font(_scaled(size, k), weight)
            if all(small.getlength(p) <= width for p in parts):
                return parts, small
    # 区切りの無い文言（例「ユーザー登録 本文に「id=…」が無い」）は、1 行に収まるならそのまま出す。2026-11-02 までは
    # 字数の折り返しへ進み、17 ピクセルで 1 行に収まると 2 行目が空のまま 2 行分の帯になって、下の隙間が大きかった
    for size in range(BIG_SMALL, BIG_MIN - 1, -1):
        small = font(_scaled(size, k), weight)
        if small.getlength(text) <= width:
            return [text], small
    small = font(_scaled(BIG_MIN, k), weight)
    first = ""
    for ch in text:
        if small.getlength(first + ch) > width:
            break
        first += ch
    rest = text[len(first):]
    while rest and small.getlength(rest) > width:
        rest = rest[:-2] + "…"
    return [first, rest], small


BIG_BOX = {1: (3, 41), 2: (2, 54)}  # 大きな異常の文言の帯の上端と下端（行の数ごと。帯の無いオレンジの文言もこの中に置く）
BIG_STEP = 22  # 2 行のときの基準線の間


def _centered_baselines(lines: list[str], f, top: float, bottom: float, k: float = 1.0) -> list[float]:
    """``top``〜``bottom`` の中で、字（1 行目の上端から最後の行の下端まで）の上下の隙間が等しくなる基準線。

    字の上端と下端は、その文言をそのフォントで描いたときの実寸で測る（寸法は 3.5 インチの値。``f`` は k 倍の大きさ）。
    2026-11-02 までは基準線を決め打ち（1 行 31、2 行 25・47）にしていたので、24 ピクセルより小さい字は下に寄った。
    """
    ink_top = f.getbbox(lines[0], anchor="ls")[1] / k
    ink_bottom = f.getbbox(lines[-1], anchor="ls")[3] / k
    span = BIG_STEP * (len(lines) - 1)
    first = (top + bottom - span - ink_top - ink_bottom) / 2
    return [first + BIG_STEP * i for i in range(len(lines))]


def _alert_text(assessment: Assessment) -> str:
    rest = len(assessment.alerts) - 1
    return assessment.alerts[0] + (f"　ほか {rest} 件" if rest else "")


def render(status: ServerStatus | None, assessment: Assessment | None, config: MonitorConfig,
           fetch_error: str | None = None, portrait: bool = False, note: str | None = None,
           layout: _Layout | None = None) -> Image.Image:
    """``status`` は最後に取れた値（まだ無ければ None）。``fetch_error`` は直近の取得の失敗の説明。

    ``note`` は、異常が無いときに見出しの行へ緑の点と出す文言（無ければ、監視の状態があるとき「監視 正常」）。
    この Mac の状態の画面が、最後のバックアップの時刻を出すのに使う。
    ``layout`` を渡すと、``portrait`` の代わりにその配置で描く。
    """
    layout = layout or (PORTRAIT if portrait else LANDSCAPE)
    width = layout.size[0]
    # 配置は 3.5 インチの寸法で決め、描くときに k 倍する。length は画面のピクセルの幅を 3.5 インチの寸法に戻す
    k = layout.k
    at = (lambda x, y: (x, y)) if k == 1 else (lambda x, y: (x * k, y * k))
    sized = lambda size: _scaled(size, k)  # noqa: E731
    length = lambda f, text: f.getlength(text) / k  # noqa: E731
    fit = lambda text, room, size, weight: fit_font(text, room * k, sized(size), weight)  # noqa: E731
    red = assessment is not None and assessment.red
    background = RED if red else BACKGROUND
    faint = _mix(WHITE, RED, 0.45) if red else SECONDARY
    divider = _mix(WHITE, RED, 0.22) if red else CARD
    alerting = assessment.alerting_metrics if assessment else frozenset()
    metrics = status.metrics if status else ()
    specs = [m.spec for m in metrics] or list(config.metrics)
    ring_x, ring_y, radius, ring_width = layout.ring

    shapes = _Shapes(layout.size, background, k)
    for index, spec in enumerate(specs):
        x, y = layout.cells[index]
        value = metrics[index].value if metrics else None
        if red:
            color = WHITE if spec.label in alerting else faint
            track = _mix(WHITE, RED, 0.22)
        else:
            tint = "normal" if value is None else (metrics[index].tint or warning_tint(value, spec.threshold))
            color = {"normal": BLUE, "warning": ORANGE, "critical": RED}[tint]
            track = _mix(SECONDARY if value is None else color, BACKGROUND, DARK_TRACK_MIX)
        shapes.ring(x + ring_x, y + ring_y, radius, ring_width, value, color, track)
    # 見出しの名前。横置きは監視の状態が名前と同じ行にあるので、名前が帯にかかるときは帯と文言を右へ寄せる
    # （名前が短ければ帯は中央のまま。ロゴを付ける前から、見本の example.com の末尾が帯に隠れていた）
    title_left = layout.inset + (ICON_SIZE + ICON_GAP if config.logo else 0)
    same_row = layout.pill[1] < layout.title_baseline
    stamp = f"{status.fetched_at.astimezone(JST):%H:%M} " + ("時点" if fetch_error else "更新") if status else ""
    stamp_font = font(sized(layout.stamp_size), SMALL_WEIGHT)
    title_right = width / 2 if same_row else width - layout.inset - length(stamp_font, stamp) - TITLE_GAP
    title_font = fit(config.title, title_right - title_left, 15, 6)
    pill = layout.pill
    if same_row:
        pill = (max(pill[0], round(title_left + length(title_font, config.title) + TITLE_GAP)), *pill[1:])
    # 異常の文言を大きく出す設定（横置きだけ）: 異常のあるときだけ、見出しのロゴ・名前・右上の時刻を出さず、
    # 見出しの行をまるごと帯と文言に使う（2026-11-02 ユーザーの指示。それまでは名前だけを消していた）。
    # 異常が無いときは、ロゴ・名前・時刻を出し、点と短い文言のまま
    big_text = None
    if config.large_alerts and not portrait:
        big_text = _alert_text(assessment) if red else (
            fetch_error or (assessment.warnings[0] if assessment and assessment.warnings else None))
    big = bool(big_text)
    if big:
        pill = (layout.inset, pill[1], round(width - layout.inset), pill[3])
    center = (pill[0] + pill[2]) / 2

    # 監視の状態: 赤の状態は白い帯にアラート、それ以外は点と短い文言
    pill_width = pill[2] - pill[0]
    message = message_font = message_left = None
    warn = False
    big_lines = big_font = None
    if big:
        big_lines, big_font = _big_lines(big_text, (pill_width - 24) * k, 6 if red else SMALL_WEIGHT, k)
    two_lines = red and layout.tall_pill is not None and len(assessment.alerts) > 1
    if big_lines:
        if red:
            top, bottom = BIG_BOX[len(big_lines)]
            box = (pill[0], top, pill[2], bottom)
            shapes.pill(box, WHITE, radius=(box[3] - box[1]) / 2 if len(big_lines) == 1 else 14)
    elif two_lines:
        shapes.pill(layout.tall_pill, WHITE, radius=16)
    elif red:
        shapes.pill(pill, WHITE)
    else:
        message = fetch_error or (assessment.warnings[0] if assessment and assessment.warnings else None)
        warn = message is not None
        if message is None and status:
            message = note if note is not None else ("監視 正常" if status.monitor is not None else None)
        if message:
            dot_space = layout.dot_radius * 2 + 5
            message_font = fit(message, pill_width - 20, layout.status_size, SMALL_WEIGHT)
            message_left = center - (length(message_font, message) + dot_space) / 2 + dot_space
            shapes.circle(message_left - layout.dot_radius - 5, layout.dot_y, layout.dot_radius,
                          ORANGE if warn else GREEN)
    # 件数の行の図形（0 の線と 1 時間ごとの棒）。警報の条件を満たした時間の棒は赤（赤の画面では白か薄い色）
    rows = layout.counter_rows
    counters = status.counters if status else ()
    counter_specs = [c.spec for c in counters] or list(config.counters)
    if rows is not None:
        spark_x, spark_w, spark_h, spark_bottom = rows.spark
        step, one = spark_w / 24, 1 / k  # 1 は画面の 1 ピクセル
        for index, spec in enumerate(counter_specs):
            counter = counters[index] if counters else None
            bottom = rows.top + rows.height * index + spark_bottom
            shapes.pill((spark_x, bottom - one, spark_x + spark_w, bottom), divider if red else _mix(SECONDARY, BACKGROUND, 0.45),
                        radius=0)
            if counter is None:
                continue
            strong = WHITE if spec.label in alerting else faint
            peak = max(spec.alert_at, *counter.hourly, 1)
            for hour, (count, alarmed) in enumerate(zip(counter.hourly, counter.alert_hours)):
                if count > 0:
                    height = max(5 * one, spark_h * count / peak)
                    color = strong if red else (RED if alarmed else LABEL)
                    shapes.pill((spark_x + hour * step + 2 * one, bottom - height, spark_x + (hour + 1) * step - 2 * one,
                                 bottom), color, radius=2 * one)
    image = shapes.finish()
    draw = ImageDraw.Draw(image)

    # 見出し
    ink = WHITE if red else LABEL
    if not big:
        if config.logo:
            paste_mark(image, _logo(config.logo), *at(layout.inset, layout.title_baseline - LOGO_RISE),
                       sized(ICON_SIZE))
        draw.text(at(title_left, layout.title_baseline), config.title, font=title_font, fill=ink, anchor="ls")
        if stamp:
            draw.text(at(width - layout.inset, layout.title_baseline), stamp, font=stamp_font, fill=ink, anchor="rs")
    if big_lines:
        baselines = _centered_baselines(big_lines, big_font, *BIG_BOX[len(big_lines)], k)
        for text, baseline in zip(big_lines, baselines):
            draw.text(at(center, baseline), text, font=big_font, fill=RED if red else ORANGE, anchor="ms")
    elif two_lines:
        first, second = layout.tall_baselines
        text = assessment.alerts[0]
        draw.text(at(center, first), text, font=fit(text, pill_width - 24, layout.alert_size, 6), fill=RED,
                  anchor="ms")
        draw.text(at(center, second), f"ほか {len(assessment.alerts) - 1} 件", font=font(sized(15), 6), fill=RED,
                  anchor="ms")
    elif red:
        text = _alert_text(assessment)
        draw.text(at(center, layout.status_baseline - 1 if not portrait else layout.status_baseline + 1), text,
                  font=fit(text, pill_width - 24, layout.alert_size, 6), fill=RED, anchor="ms")
    elif message:
        draw.text(at(message_left, layout.status_baseline), message, font=message_font,
                  fill=ORANGE if warn else LABEL, anchor="ls")

    # 2×2
    for x0, y0, x1, y1 in layout.dividers:
        draw.line((*at(x0, y0), *at(x1, y1)), fill=divider, width=sized(1))
    label_x, label_y, label_anchor, label_size = layout.label
    number_x, number_y, number_size, unit_size, centered = layout.number
    threshold_x, threshold_y, threshold_anchor, threshold_size = layout.threshold
    for index, spec in enumerate(specs):
        x, y = layout.cells[index]
        value = metrics[index].value if metrics else None
        strong = WHITE if (not red or spec.label in alerting) else faint
        draw.text(at(x + label_x, y + label_y), spec.label, font=font(sized(label_size), 6), fill=strong,
                  anchor=label_anchor)
        number = "--" if value is None else f"{value:.0f}"
        number_font = rounded(sized(number_size))
        unit_font = rounded(sized(unit_size)) if unit_size > 0 else None
        number_width = length(number_font, number)
        gap = 1 if centered else 2
        sign = value is not None and unit_size > 0
        unit_width = length(unit_font, "%") + gap if sign else 0
        left = x + number_x - ((number_width + unit_width) / 2 if centered else 0)
        draw.text(at(left, y + number_y), number, font=number_font, fill=strong, anchor="ls")
        if sign:
            draw.text(at(left + number_width + gap, y + number_y), "%", font=unit_font, fill=faint, anchor="ls")
        detail = metrics[index].detail if metrics and metrics[index].detail is not None else None
        lines = detail if detail is not None else (f"しきい値 {spec.threshold:g}%",)
        line_step = max(DETAIL_LINE, threshold_size + 4)  # 14 ピクセルまでは 18、大きくしたら字に合わせて広げる
        for line_index, line in enumerate(lines):
            draw.text(at(x + threshold_x, y + threshold_y + line_step * line_index), line,
                      font=font(sized(threshold_size), SMALL_WEIGHT), fill=faint, anchor=threshold_anchor)

    # 小見出し（灰色）。異常の文言の帯にかかるものは描かない（2 行の帯は「サーバー」の小見出しまで伸びる）
    for hx, hy, text, size, weight, anchor in layout.headings:
        if big_lines and hy - size <= BIG_BOX[len(big_lines)][1]:
            continue
        draw.text(at(hx, hy), text, font=font(sized(size), weight), fill=faint, anchor=anchor)

    # 件数の行: 左に名前、右に直近 24 時間の件数（警報の条件を満たした時間があれば赤）
    if rows is not None:
        for index, spec in enumerate(counter_specs):
            counter = counters[index] if counters else None
            top = rows.top + rows.height * index
            if index:
                draw.line((*at(rows.left, top), *at(rows.right, top)), fill=divider, width=sized(1))
            strong = WHITE if (not red or spec.label in alerting) else faint
            baseline = top + rows.baseline
            draw.text(at(rows.left, baseline), spec.label, font=font(sized(rows.label_size), 6), fill=strong,
                      anchor="ls")
            unit_font = font(sized(rows.unit_size), SMALL_WEIGHT)
            number = "--" if counter is None else f"{counter.total:g}"
            if counter is not None:
                draw.text(at(rows.right, baseline), "件", font=unit_font, fill=faint, anchor="rs")
            number_right = rows.right - (length(unit_font, "件") + 6 / k if counter is not None else 0)
            alarmed = counter is not None and any(counter.alert_hours)
            draw.text(at(number_right, baseline), number, font=rounded(sized(rows.number_size)),
                      fill=strong if red else (RED if alarmed else LABEL), anchor="rs")
    return image
