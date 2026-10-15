"""ゲージ型の画面（既定）。

Apple のウィジェット（バッテリー）とアクティビティのリングを手本にした。上端に見出しを置き、
その下にカード 3 枚を並べて、カードごとに円形のゲージ・使用率・リセット時刻を出す。
5.2 インチはカードの面を描かず、黒地に縦の区切り線で 3 つに分ける（``Layout.cards``。2026-10-15）。

- 色は Human Interface Guidelines（Color）のダークモードのシステムカラー（2025-06-09 更新の値）
- 文字の大きさは HIG（Typography）の iOS 既定の文字スタイルの pt を、そのままピクセルで使う。
  3.5 インチ（480×320）は iPhone 3GS（3.5 インチ・480×320・163 ppi）と同じ大きさなので、
  iPhone で見る文字とほぼ同じ大きさになる
- ほかの大きさの画面では、寸法と文字の大きさを高さの比（高さ ÷ 320）で拡大し、増えた横幅はカードの幅に回す。
  そのうえで、カードの中身（リング・数字・文字）は ``LARGE`` の倍率でさらに大きくする（``layout_for``）
  5.2 インチ（1280×720、約 282 ppi）は 2.25 倍で、文字は 3.5 インチより約 1.3 倍大きく見える
  （2.25 × 165 ÷ 282）。表示部の高さも 49 mm から 62 mm へ約 1.27 倍になるので、縦の配分は変わらない
- 図形は拡大して描いてから縮め、縁を滑らかにする。文字は縮めるとかすれるため、縮めた後に等倍で書く
- ``render_with_gemini`` は、Antigravity の Gemini の枠を足した画面。上の段に Claude Code の 3 枚、下の段に
  Gemini の 2 枚（横長のカードの左にリング）を置く（2026-10-11 にユーザーが見本の 2 案から選んだ「案 B」）。
  下の段の見出しは出どころの「Antigravity」、カードの名前は「Gemini 5時間」「Gemini 週次」
  （Gemini アプリや Gemini CLI の枠と区別するため。2026-10-13 ユーザーが決定）
- 見出しの左に、Claude と Gemini のアイコンを出せる（``load_icons``）。ロゴはリポジトリに入れず、
  この Mac のフォルダから読む。Anthropic と Google の商標の指針は、ロゴの使用に承認を求めるため（README「アイコン」）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import lru_cache

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .render import (CRITICAL_AT, HEIGHT, JST, SMALL_WEIGHT, WARNING_AT, WEEKDAYS, WIDTH, fit_font, font,
                     format_remaining, nearest_minute)
from .usage import Meter, Snapshot

SCALE = 4  # 3.5 インチの画面で図形を描く倍率。大きい画面では、描く大きさが同じくらいになるよう下げる

BACKGROUND = (0, 0, 0)
# HIG の Gray (6) は (28, 28, 30) だが、RGB565（赤・青 5 ビット、緑 6 ビット）では (24, 28, 24) になり緑に寄る。
# RGB565 でそのまま表せる無彩色のうち近いもの（液晶で黒地との差が見えやすい明るい側）を使う
CARD = (33, 32, 33)
LABEL = (255, 255, 255)
SECONDARY = (142, 142, 147)  # Gray
BLUE = (0, 145, 255)
ORANGE = (255, 146, 48)
RED = (255, 66, 69)
TRACK_MIX = 0.25  # ゲージの軌道は、ゲージの色をカードの面へ 75% 寄せる
DARK_TRACK_MIX = 0.22  # 黒地に直接描くときは、ゲージの色を黒へ 78% 寄せる（サーバーの状態の画面と同じ）

# HIG の文字スタイル（iOS 既定の大きさ）
TITLE1 = 28
SUBHEAD = 15
FOOTNOTE = 13
CAPTION1 = 12

ROUNDED_FONT = "/System/Library/Fonts/SFNSRounded.ttf"

# 3.5 インチ（480×320）での寸法。ほかの大きさの画面では Layout が高さの比で拡大する
MARGIN = 12
HEADER_INSET = 20
HEADER_BASELINE = 25
CARD_TOP = 36
CARD_GAP = 8
CARD_RADIUS = 18
CARD_PADDING = 10
REMAIN_GAP = 27  # リセットの日時と残り時間の間（基準線どうし）。間を空け、残り時間を別の情報として読ませる
CARD_WIDTH = (WIDTH - MARGIN * 2 - CARD_GAP * 2) / 3
RING_RADIUS = 50
RING_WIDTH = 11
STATUS_GAP = 12
ICON_SIZE = 20  # 見出しのアイコンの一辺
ICON_GAP = 6

# Gemini を足した画面（render_with_gemini）の寸法。5.2 インチの見本（1280×720）の値を 2.25 で割ったもの
UPPER_CARD_BOTTOM = 201        # 上の段（Claude Code）のカードの下端
UPPER_RING_RADIUS = 41
UPPER_RING_WIDTH = 10
UPPER_NUMBER = 23              # リングの中の数字（TITLE1 の 0.82 倍）
GEMINI_BASELINE = 226          # 下の段の見出し
LOWER_CARD_TOP = 235.5
LOWER_RING_RADIUS = 27.5
LOWER_RING_WIDTH = 7
LOWER_NUMBER = 17              # TITLE1 の 0.62 倍


@dataclass(frozen=True)
class Layout:
    """画面の大きさに合わせた寸法。``content`` はカードの中身の倍率、``stamp`` は見出しの右の時刻の大きさ（pt）。"""

    width: int = WIDTH
    height: int = HEIGHT
    content: float = 1.0
    stamp: int = FOOTNOTE
    quiet_remain: bool = False  # 残り時間を「リセット」の見出しと同じ灰色の小さい字にする
    blue: tuple[int, int, int] = BLUE  # リングの弧の青（地は BLUE から作る）
    cards: bool = True  # False はカードの面を描かず、黒地に縦の区切り線を引く
    ring: float = 1.0  # リングの半径と太さの倍率（content に掛ける）。大きくした分は下へ伸ばす
    remain_gap: float = REMAIN_GAP  # リセットの日時と残り時間の間（3.5 インチの寸法。content を掛ける）

    @property
    def k(self) -> float:
        """3.5 インチの画面に対する倍率（高さの比）。"""
        return self.height / HEIGHT

    def px(self, value: float) -> float:
        return value * self.k

    def pt(self, size: float) -> int:
        return round(size * self.k)

    def cpx(self, value: float) -> float:
        """カードの中身の寸法。"""
        return self.px(value * self.content)

    def cpt(self, size: float) -> int:
        """カードの中身の文字の大きさ。"""
        return self.pt(size * self.content)

    def ring_px(self) -> tuple[float, float]:
        """3 枚の画面のリングの半径と太さ（ピクセル）。"""
        return self.cpx(RING_RADIUS) * self.ring, self.cpx(RING_WIDTH) * self.ring

    @property
    def supersample(self) -> int:
        return max(2, round(SCALE / self.k))

    @property
    def card_width(self) -> float:
        return (self.width - self.px(MARGIN) * 2 - self.px(CARD_GAP) * 2) / 3


# 大きい画面での調整（高さの比の拡大に加える）。3.5 インチ（480×320）は変えない
# - content: 5.2 インチは余白が大きかったので、3.5 インチのサーバー監視の画面と同じように、カードの中身を大きくした
#   （2026-10-13 ユーザーの指示）
# - stamp: 3.5 インチのサーバー監視の画面（縦置き）の名前 15・時刻 16 と同じ比にする（2026-10-13 ユーザーの指示）
# - quiet_remain: 「あと…」を「リセット」の見出しと同じ書き方にする（2026-10-13、ユーザーが見本の 2 案から選んだ）。
#   3.5 インチでは「薄くて見えない」として白にした（2026-10-09）うえ、12 ピクセルの W3 は「4」の横棒が消えるので変えない
# - blue: 5.2 インチのパネルでは、3.5 インチと同じ青の弧が暗く見えたので、緑を減らした濃い青にした
#   （2026-10-15、ユーザーが実機で候補 5 つから選んだ）。5.2 インチは PNG で送るので、RGB565 に落ちない
# - cards: カードの面の薄い灰色が、3.5 インチのサーバーの状態の画面（黒地）と色が違って見える原因の 1 つだったので、
#   カードをやめて黒地にし、同じ画面と同じく薄い縦の区切り線を引く（2026-10-15 ユーザーの指示）
# - ring・remain_gap: カードが無くなって下の隙間が目立ったので、リングを 1.15 倍にして「リセット」以降を下げ、
#   「あと…」を日時に寄せた（日時との隙間 24 px は「リセット」と日時の隙間と同じ。下の余白は左右と同じ 27 px）。
#   名前の位置は変えていない（2026-10-15、ユーザーが実機で候補から選んだ）
LARGE = {(1280, 720): {"content": 1.2, "stamp": 16, "quiet_remain": True, "blue": (0, 105, 255), "cards": False,
                       "ring": 1.15, "remain_gap": 22}}


def layout_for(size: tuple[int, int]) -> Layout:
    return Layout(*size, **LARGE.get(tuple(size), {}))


def _remain_style(layout: Layout, scaled: bool = True) -> tuple[int, int, tuple[int, int, int]]:
    """残り時間（「あと…」）の字の大きさ（ピクセル）・太さ・色。``scaled`` はカードの中身の倍率を掛けるか。"""
    size = (layout.cpt if scaled else layout.pt)(CAPTION1 if layout.quiet_remain else FOOTNOTE)
    if layout.quiet_remain:  # 「リセット」の見出しと同じ（13 ピクセル以下になるときだけ W4）
        return size, 3 if size > 13 else SMALL_WEIGHT, SECONDARY
    return size, SMALL_WEIGHT, LABEL


@lru_cache(maxsize=None)
def rounded(size: int, weight: str = "Semibold") -> ImageFont.FreeTypeFont:
    """数字用の SF Pro Rounded。無い macOS ではヒラギノ角ゴシック W6 で代える。"""
    try:
        f = ImageFont.truetype(ROUNDED_FONT, size)
        f.set_variation_by_name(weight)
        return f
    except (OSError, ValueError):
        return font(size, 6)


def tint(percent: float) -> tuple[int, int, int]:
    if percent >= CRITICAL_AT:
        return RED
    if percent >= WARNING_AT:
        return ORANGE
    return BLUE


def _mix(color, base, ratio: float) -> tuple[int, int, int]:
    return tuple(round(c * ratio + b * (1 - ratio)) for c, b in zip(color, base))


def reset_lines(resets_at: datetime | None, now: datetime) -> tuple[str, str]:
    """リセットの日時と残り時間の 2 行。時刻は iOS の日本語表記にならい、時の先頭に 0 を付けない。"""
    if resets_at is None:
        return "--", ""
    resets_at = nearest_minute(resets_at)
    if resets_at <= now:
        return "リセット済み", "次の取得で更新"
    local = resets_at.astimezone(JST)
    clock = f"{local.hour}:{local.minute:02d}"
    if resets_at - now < timedelta(hours=24) and local.date() == now.astimezone(JST).date():
        when = clock
    else:
        when = f"{local.month}/{local.day}({WEEKDAYS[local.weekday()]}) {clock}"
    return when, format_remaining(resets_at - now)


@lru_cache(maxsize=None)
def content_rows(layout: Layout = Layout()) -> tuple[float, float, float, float, float, float]:
    """カードの中身の各行の位置（中身の上端から測る）と、中身の高さ。

    上端は見出しの字の上端、下端は残り時間の字の下端で、どちらもフォントの実寸で測る。
    """
    cpx = layout.cpx
    ascent = -font(layout.cpt(SUBHEAD), 6).getbbox("時", anchor="ls")[1]
    remain_size, remain_weight, _color = _remain_style(layout)
    descent = font(remain_size, remain_weight).getbbox("あと", anchor="ls")[3]
    radius = cpx(RING_RADIUS) * layout.ring
    label = ascent
    ring_center = label + cpx(16) + radius
    caption = ring_center + radius + cpx(28)
    when = caption + cpx(22)
    remain = when + cpx(layout.remain_gap)
    return label, ring_center, caption, when, remain, remain + descent


def content_top(layout: Layout = Layout()) -> float:
    """カードの中身の上端。リングが等倍のときの中身をカードの高さの中央に置く位置で、
    リングの大きさや残り時間の間を変えても名前の位置は変えず、下の行だけを動かす。"""
    _left, top, _right, bottom = card_box(0, layout)
    return top + (bottom - top - content_rows(replace(layout, ring=1.0, remain_gap=REMAIN_GAP))[-1]) / 2


def card_box(index: int, layout: Layout = Layout()) -> tuple[float, float, float, float]:
    left = layout.px(MARGIN) + index * (layout.card_width + layout.px(CARD_GAP))
    return left, layout.px(CARD_TOP), left + layout.card_width, layout.height - layout.px(MARGIN)


def dividers(layout: Layout) -> list[tuple[float, float, float, float]]:
    """カードを描かないときの縦の区切り線（カードの間の中央、カードと同じ高さ）。"""
    lines = []
    for index in range(2):
        _left, top, right, bottom = card_box(index, layout)
        x = (right + card_box(index + 1, layout)[0]) / 2
        lines.append((x, top, x, bottom))
    return lines


class _Shapes:
    """図形を拡大して描く下書き。"""

    def __init__(self, layout: Layout):
        self.layout = layout
        self.scale = layout.supersample
        self.image = Image.new("RGB", (layout.width * self.scale, layout.height * self.scale), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)

    def _box(self, x0, y0, x1, y1):
        return x0 * self.scale, y0 * self.scale, x1 * self.scale, y1 * self.scale

    def rounded_rectangle(self, box, radius, fill):
        self.draw.rounded_rectangle(self._box(*box), radius * self.scale, fill=fill)

    def circle(self, cx, cy, r, fill):
        self.draw.ellipse(self._box(cx - r, cy - r, cx + r, cy + r), fill=fill)

    def ring(self, cx, cy, percent: float | None, radius: float = RING_RADIUS, ring_width: float = RING_WIDTH,
             surface: tuple[int, int, int] = CARD):
        """12 時の位置から時計回りに伸びる、端の丸いリング。半径と太さは 3.5 インチでの寸法。

        ``surface`` はリングの下の色（カードの面か黒地）。地はゲージの色をそこへ寄せて作る。
        """
        radius, ring_width = self.layout.px(radius), self.layout.px(ring_width)
        color = BLUE if percent is None else tint(percent)
        track = _mix(SECONDARY if percent is None else color, surface, TRACK_MIX if surface == CARD else DARK_TRACK_MIX)
        if color == BLUE:
            color = self.layout.blue
        box = self._box(cx - radius, cy - radius, cx + radius, cy + radius)
        width = round(ring_width * self.scale)
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
        return self.image.resize((self.layout.width, self.layout.height), Image.LANCZOS)


def _value(draw: ImageDraw.ImageDraw, cx: float, baseline: float, percent: float | None, layout: Layout,
           number_size: int = TITLE1, unit_size: int = SUBHEAD) -> None:
    """「26」を大きく、「%」を小さく灰色で、ベースラインをそろえて中央に書く。"""
    number = "--" if percent is None else f"{round(percent)}"
    number_font, unit_font = rounded(layout.pt(number_size)), rounded(layout.pt(unit_size))
    number_width = draw.textlength(number, font=number_font)
    unit_width = 0 if percent is None else draw.textlength("%", font=unit_font) + layout.px(1)
    left = cx - (number_width + unit_width) / 2
    draw.text((left, baseline), number, font=number_font, fill=LABEL, anchor="ls")
    if percent is not None:
        draw.text((left + number_width + layout.px(1), baseline), "%", font=unit_font, fill=SECONDARY, anchor="ls")


def load_icons(directory: str | Path) -> dict[str, Image.Image]:
    """``directory`` の ``claude.png`` と ``gemini.png`` を読む。無いものは飛ばす。周りの透明な余白は切り落とす。"""
    icons = {}
    for name in ("claude", "gemini"):
        path = Path(directory) / f"{name}.png"
        if path.is_file():
            image = Image.open(path).convert("RGBA")
            icons[name] = image.crop(image.getbbox() or (0, 0, *image.size))
    return icons


def _badge(layout: Layout, baseline: float) -> tuple[float, float]:
    """取得に失敗したときに見出しの左に出す、オレンジの丸の中心。``baseline`` は 3.5 インチでの寸法。"""
    return layout.px(HEADER_INSET) + layout.px(7), layout.px(baseline) - layout.px(5.5)


def _header(image: Image.Image, draw: ImageDraw.ImageDraw, layout: Layout, baseline_units: float, title: str,
            snapshot: Snapshot | None, status: str | None, icon: Image.Image | None = None,
            stamp_size: int = FOOTNOTE) -> None:
    """見出しの行。左に名前（取得に失敗したときは、オレンジの丸とその説明）、右に取得の時刻。

    オレンジの丸は図形の下書きに描いておく（``_badge``）。``stamp_size`` は右の時刻の大きさ（3.5 インチでの pt）。
    """
    px, pt = layout.px, layout.pt
    width = layout.width
    inset, baseline = px(HEADER_INSET), px(baseline_units)
    badge = _badge(layout, baseline_units)
    small = font(pt(stamp_size), SMALL_WEIGHT)
    fetched = f"{snapshot.fetched_at.astimezone(JST):%H:%M}" if snapshot else ""
    if status:
        when = f"{fetched} 時点" if snapshot else ""
        draw.text((width - inset, baseline), when, font=small, fill=LABEL, anchor="rs")
        draw.text((badge[0], badge[1] + px(4.5)), "!", font=rounded(pt(CAPTION1), "Bold"), fill=BACKGROUND,
                  anchor="ms")
        message_left = inset + px(20)
        reserved = small.getlength(when) + px(STATUS_GAP) if when else 0
        draw.text((message_left, baseline), status,
                  font=fit_font(status, width - inset - message_left - reserved, pt(FOOTNOTE), SMALL_WEIGHT),
                  fill=ORANGE, anchor="ls")
        return
    left = inset
    if icon is not None:
        side = round(px(ICON_SIZE))
        mark = icon.copy()
        mark.thumbnail((side, side), Image.LANCZOS)
        center_y = badge[1]  # 名前の字の高さの中ほど
        image.paste(mark, (round(left + (side - mark.width) / 2), round(center_y - mark.height / 2)), mark)
        left += side + px(ICON_GAP)
    draw.text((left, baseline), title, font=font(pt(SUBHEAD), 6), fill=LABEL, anchor="ls")
    if snapshot:
        draw.text((width - inset, baseline), f"{fetched} 更新", font=small, fill=LABEL, anchor="rs")


def render(snapshot: Snapshot | None, now: datetime, status: str | None = None,
           labels: tuple[str, ...] = ("5時間", "週次", "Fable週次"),
           size: tuple[int, int] = (WIDTH, HEIGHT), icons: dict[str, Image.Image] | None = None) -> Image.Image:
    """``status`` は取得に失敗したときの短い説明。前回の値を残したまま、見出しの位置に出す。

    ``icons`` は ``load_icons`` の結果。``claude`` があれば見出しの名前の左に出す。
    """
    layout = layout_for(size)
    px, cpx, cpt = layout.px, layout.cpx, layout.cpt
    width = layout.width
    meters = snapshot.meters[:3] if snapshot else tuple(Meter(label, None, None) for label in labels)
    label_y, ring_y, caption_y, when_y, remain_y, _content_height = content_rows(layout)

    shapes = _Shapes(layout)
    centers = []
    for index, meter in enumerate(meters):
        left, top, right, bottom = card_box(index, layout)
        if layout.cards:
            shapes.rounded_rectangle((left, top, right, bottom), px(CARD_RADIUS), CARD)
        origin = content_top(layout)
        cx = (left + right) / 2
        percent = None if meter.percent is None else max(0.0, min(100.0, meter.percent))
        shapes.ring(cx, origin + ring_y, percent, RING_RADIUS * layout.content * layout.ring,
                    RING_WIDTH * layout.content * layout.ring, CARD if layout.cards else BACKGROUND)
        centers.append((cx, origin))
    if status:
        shapes.circle(*_badge(layout, HEADER_BASELINE), px(7), ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)
    if not layout.cards:
        for line in dividers(layout):
            draw.line(line, fill=CARD, width=max(1, round(px(1))))
    _header(image, draw, layout, HEADER_BASELINE, "Claude Code", snapshot, status, (icons or {}).get("claude"),
            layout.stamp)

    inner = layout.card_width - px(CARD_PADDING) * 2
    for (cx, origin), meter in zip(centers, meters):
        draw.text((cx, origin + label_y), meter.label, font=fit_font(meter.label, inner, cpt(SUBHEAD), 6),
                  fill=LABEL, anchor="ms")
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, origin + ring_y + cpx(10), percent, layout, TITLE1 * layout.content,
               SUBHEAD * layout.content)
        when, remain = reset_lines(meter.resets_at, now)
        draw.text((cx, origin + caption_y), "リセット", font=font(cpt(CAPTION1), 3), fill=SECONDARY, anchor="ms")
        draw.text((cx, origin + when_y), when, font=fit_font(when, inner, cpt(SUBHEAD), 6), fill=LABEL, anchor="ms")
        remain_size, remain_weight, remain_color = _remain_style(layout)
        draw.text((cx, origin + remain_y), remain, font=fit_font(remain, inner, remain_size, remain_weight),
                  fill=remain_color, anchor="ms")
    return image


def _upper_rows(layout: Layout) -> tuple[float, float, float, float, float]:
    """上の段のカードの中身の各行の位置（中身の上端から測る）と、中身の高さ。"""
    px = layout.px
    ascent = -font(layout.pt(SUBHEAD), 6).getbbox("時", anchor="ls")[1]
    remain_size, remain_weight, _color = _remain_style(layout, scaled=False)
    descent = font(remain_size, remain_weight).getbbox("あと", anchor="ls")[3]
    label = ascent
    ring_center = label + px(10) + px(UPPER_RING_RADIUS)
    when = ring_center + px(UPPER_RING_RADIUS) + px(25)
    remain = when + px(18.5)
    return label, ring_center, when, remain, remain + descent


def _reset_text(when: str) -> str:
    return f"リセット {when}"


def render_with_gemini(snapshot: Snapshot | None, gemini: Snapshot | None, now: datetime,
                       status: str | None = None, gemini_status: str | None = None,
                       labels: tuple[str, ...] = ("5時間", "週次", "Fable週次"),
                       gemini_labels: tuple[str, ...] = ("Gemini 5時間", "Gemini 週次"),
                       size: tuple[int, int] = (WIDTH, HEIGHT),
                       icons: dict[str, Image.Image] | None = None) -> Image.Image:
    """上の段に Claude Code の 3 枚、下の段に Antigravity の Gemini の枠の 2 枚を出す。

    ``gemini_status`` は Gemini の取得に失敗したときの短い説明で、下の段の見出しに出す。
    """
    layout = layout_for(size)
    px, pt = layout.px, layout.pt
    icons = icons or {}
    meters = snapshot.meters[:3] if snapshot else tuple(Meter(label, None, None) for label in labels)
    gemini_meters = gemini.meters[:2] if gemini else tuple(Meter(label, None, None) for label in gemini_labels)
    label_y, ring_y, when_y, remain_y, content_height = _upper_rows(layout)

    shapes = _Shapes(layout)
    upper = []
    for index, meter in enumerate(meters):
        left, top, right, _bottom = card_box(index, layout)
        bottom = px(UPPER_CARD_BOTTOM)
        shapes.rounded_rectangle((left, top, right, bottom), px(CARD_RADIUS), CARD)
        origin = top + (bottom - top - content_height) / 2
        cx = (left + right) / 2
        percent = None if meter.percent is None else max(0.0, min(100.0, meter.percent))
        shapes.ring(cx, origin + ring_y, percent, UPPER_RING_RADIUS, UPPER_RING_WIDTH)
        upper.append((cx, origin))
    lower = []
    lower_width = (layout.width - px(MARGIN) * 2 - px(CARD_GAP)) / 2
    for index, meter in enumerate(gemini_meters):
        left = px(MARGIN) + index * (lower_width + px(CARD_GAP))
        top, bottom = px(LOWER_CARD_TOP), layout.height - px(MARGIN)
        shapes.rounded_rectangle((left, top, left + lower_width, bottom), px(CARD_RADIUS), CARD)
        cx, cy = left + px(15) + px(LOWER_RING_RADIUS), (top + bottom) / 2
        percent = None if meter.percent is None else max(0.0, min(100.0, meter.percent))
        shapes.ring(cx, cy, percent, LOWER_RING_RADIUS, LOWER_RING_WIDTH)
        lower.append((left, cx, cy))
    for baseline, failed in ((HEADER_BASELINE, status), (GEMINI_BASELINE, gemini_status)):
        if failed:
            shapes.circle(*_badge(layout, baseline), px(7), ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)
    _header(image, draw, layout, HEADER_BASELINE, "Claude Code", snapshot, status, icons.get("claude"), layout.stamp)
    _header(image, draw, layout, GEMINI_BASELINE, "Antigravity", gemini, gemini_status, icons.get("gemini"),
            layout.stamp)

    inner = layout.card_width - px(CARD_PADDING) * 2
    remain_size, remain_weight, remain_color = _remain_style(layout, scaled=False)
    for (cx, origin), meter in zip(upper, meters):
        draw.text((cx, origin + label_y), meter.label, font=fit_font(meter.label, inner, pt(SUBHEAD), 6),
                  fill=LABEL, anchor="ms")
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, origin + ring_y + px(UPPER_NUMBER * 0.36), percent, layout, UPPER_NUMBER, CAPTION1)
        when, remain = reset_lines(meter.resets_at, now)
        text = _reset_text(when)
        draw.text((cx, origin + when_y), text, font=fit_font(text, inner, pt(SUBHEAD), 6), fill=LABEL, anchor="ms")
        draw.text((cx, origin + remain_y), remain, font=fit_font(remain, inner, remain_size, remain_weight),
                  fill=remain_color, anchor="ms")
    for (left, cx, cy), meter in zip(lower, gemini_meters):
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, cy + px(LOWER_NUMBER * 0.36), percent, layout, LOWER_NUMBER, 9)
        text_left = cx + px(LOWER_RING_RADIUS) + px(18)
        width = left + lower_width - px(CARD_PADDING) - text_left
        when, remain = reset_lines(meter.resets_at, now)
        text = _reset_text(when)
        draw.text((text_left, cy - px(15)), meter.label, font=fit_font(meter.label, width, pt(SUBHEAD), 6),
                  fill=LABEL, anchor="ls")
        draw.text((text_left, cy + px(8)), text, font=fit_font(text, width, pt(SUBHEAD), 6), fill=LABEL,
                  anchor="ls")
        draw.text((text_left, cy + px(27.5)), remain, font=fit_font(remain, width, remain_size, remain_weight),
                  fill=remain_color, anchor="ls")
    return image
