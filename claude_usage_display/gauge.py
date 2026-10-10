"""ゲージ型の画面（既定）。

Apple のウィジェット（バッテリー）とアクティビティのリングを手本にした。上端に見出しを置き、
その下にカード 3 枚を並べて、カードごとに円形のゲージ・使用率・リセット時刻を出す。

- 色は Human Interface Guidelines（Color）のダークモードのシステムカラー（2025-06-09 更新の値）
- 文字の大きさは HIG（Typography）の iOS 既定の文字スタイルの pt を、そのままピクセルで使う。
  3.5 インチ（480×320）は iPhone 3GS（3.5 インチ・480×320・163 ppi）と同じ大きさなので、
  iPhone で見る文字とほぼ同じ大きさになる
- ほかの大きさの画面では、寸法と文字の大きさを高さの比（高さ ÷ 320）で拡大し、増えた横幅はカードの幅に回す。
  5.2 インチ（1280×720、約 282 ppi）は 2.25 倍で、文字は 3.5 インチより約 1.3 倍大きく見える
  （2.25 × 165 ÷ 282）。表示部の高さも 49 mm から 62 mm へ約 1.27 倍になるので、縦の配分は変わらない
- 図形は拡大して描いてから縮め、縁を滑らかにする。文字は縮めるとかすれるため、縮めた後に等倍で書く
- ``render_with_gemini`` は、Gemini（Antigravity）の枠を足した画面。上の段に Claude Code の 3 枚、下の段に
  Gemini の 2 枚（横長のカードの左にリング）を置く（2026-10-11 にユーザーが見本の 2 案から選んだ「案 B」）
- 見出しの左に、Claude と Gemini のアイコンを出せる（``load_icons``）。ロゴはリポジトリに入れず、
  この Mac のフォルダから読む。Anthropic と Google の商標の指針は、ロゴの使用に承認を求めるため（README「アイコン」）
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .render import (CRITICAL_AT, HEIGHT, JST, SMALL_WEIGHT, WARNING_AT, WEEKDAYS, WIDTH, fit_font, font,
                     format_remaining)
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
    """画面の大きさに合わせた寸法。"""

    width: int = WIDTH
    height: int = HEIGHT

    @property
    def k(self) -> float:
        """3.5 インチの画面に対する倍率（高さの比）。"""
        return self.height / HEIGHT

    def px(self, value: float) -> float:
        return value * self.k

    def pt(self, size: int) -> int:
        return round(size * self.k)

    @property
    def supersample(self) -> int:
        return max(2, round(SCALE / self.k))

    @property
    def card_width(self) -> float:
        return (self.width - self.px(MARGIN) * 2 - self.px(CARD_GAP) * 2) / 3


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
    px = layout.px
    ascent = -font(layout.pt(SUBHEAD), 6).getbbox("時", anchor="ls")[1]
    descent = font(layout.pt(FOOTNOTE), SMALL_WEIGHT).getbbox("あと", anchor="ls")[3]
    label = ascent
    ring_center = label + px(16) + px(RING_RADIUS)
    caption = ring_center + px(RING_RADIUS) + px(28)
    when = caption + px(22)
    remain = when + px(27)  # 日時との間を空け、残り時間を別の情報として読ませる
    return label, ring_center, caption, when, remain, remain + descent


def card_box(index: int, layout: Layout = Layout()) -> tuple[float, float, float, float]:
    left = layout.px(MARGIN) + index * (layout.card_width + layout.px(CARD_GAP))
    return left, layout.px(CARD_TOP), left + layout.card_width, layout.height - layout.px(MARGIN)


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

    def ring(self, cx, cy, percent: float | None, radius: float = RING_RADIUS, ring_width: float = RING_WIDTH):
        """12 時の位置から時計回りに伸びる、端の丸いリング。半径と太さは 3.5 インチでの寸法。"""
        radius, ring_width = self.layout.px(radius), self.layout.px(ring_width)
        color = BLUE if percent is None else tint(percent)
        track = _mix(SECONDARY if percent is None else color, CARD, TRACK_MIX)
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
            snapshot: Snapshot | None, status: str | None, icon: Image.Image | None = None) -> None:
    """見出しの行。左に名前（取得に失敗したときは、オレンジの丸とその説明）、右に取得の時刻。

    オレンジの丸は図形の下書きに描いておく（``_badge``）。
    """
    px, pt = layout.px, layout.pt
    width = layout.width
    inset, baseline = px(HEADER_INSET), px(baseline_units)
    badge = _badge(layout, baseline_units)
    small = font(pt(FOOTNOTE), SMALL_WEIGHT)
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
    layout = Layout(*size)
    px, pt = layout.px, layout.pt
    width = layout.width
    meters = snapshot.meters[:3] if snapshot else tuple(Meter(label, None, None) for label in labels)
    label_y, ring_y, caption_y, when_y, remain_y, content_height = content_rows(layout)

    shapes = _Shapes(layout)
    centers = []
    for index, meter in enumerate(meters):
        left, top, right, bottom = card_box(index, layout)
        shapes.rounded_rectangle((left, top, right, bottom), px(CARD_RADIUS), CARD)
        origin = top + (bottom - top - content_height) / 2
        cx = (left + right) / 2
        percent = None if meter.percent is None else max(0.0, min(100.0, meter.percent))
        shapes.ring(cx, origin + ring_y, percent)
        centers.append((cx, origin))
    if status:
        shapes.circle(*_badge(layout, HEADER_BASELINE), px(7), ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)
    _header(image, draw, layout, HEADER_BASELINE, "Claude Code", snapshot, status, (icons or {}).get("claude"))

    inner = layout.card_width - px(CARD_PADDING) * 2
    for (cx, origin), meter in zip(centers, meters):
        draw.text((cx, origin + label_y), meter.label, font=fit_font(meter.label, inner, pt(SUBHEAD), 6),
                  fill=LABEL, anchor="ms")
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, origin + ring_y + px(10), percent, layout)
        when, remain = reset_lines(meter.resets_at, now)
        draw.text((cx, origin + caption_y), "リセット", font=font(pt(CAPTION1), 3), fill=SECONDARY, anchor="ms")
        draw.text((cx, origin + when_y), when, font=fit_font(when, inner, pt(SUBHEAD), 6), fill=LABEL, anchor="ms")
        draw.text((cx, origin + remain_y), remain, font=fit_font(remain, inner, pt(FOOTNOTE), SMALL_WEIGHT),
                  fill=LABEL, anchor="ms")
    return image


def _upper_rows(layout: Layout) -> tuple[float, float, float, float, float]:
    """上の段のカードの中身の各行の位置（中身の上端から測る）と、中身の高さ。"""
    px = layout.px
    ascent = -font(layout.pt(SUBHEAD), 6).getbbox("時", anchor="ls")[1]
    descent = font(layout.pt(FOOTNOTE), SMALL_WEIGHT).getbbox("あと", anchor="ls")[3]
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
                       gemini_labels: tuple[str, ...] = ("5時間", "週次"),
                       size: tuple[int, int] = (WIDTH, HEIGHT),
                       icons: dict[str, Image.Image] | None = None) -> Image.Image:
    """上の段に Claude Code の 3 枚、下の段に Gemini（Antigravity）の 2 枚を出す。

    ``gemini_status`` は Gemini の取得に失敗したときの短い説明で、下の段の見出しに出す。
    """
    layout = Layout(*size)
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
    _header(image, draw, layout, HEADER_BASELINE, "Claude Code", snapshot, status, icons.get("claude"))
    _header(image, draw, layout, GEMINI_BASELINE, "Gemini", gemini, gemini_status, icons.get("gemini"))

    inner = layout.card_width - px(CARD_PADDING) * 2
    for (cx, origin), meter in zip(upper, meters):
        draw.text((cx, origin + label_y), meter.label, font=fit_font(meter.label, inner, pt(SUBHEAD), 6),
                  fill=LABEL, anchor="ms")
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, origin + ring_y + px(UPPER_NUMBER * 0.36), percent, layout, UPPER_NUMBER, CAPTION1)
        when, remain = reset_lines(meter.resets_at, now)
        text = _reset_text(when)
        draw.text((cx, origin + when_y), text, font=fit_font(text, inner, pt(SUBHEAD), 6), fill=LABEL, anchor="ms")
        draw.text((cx, origin + remain_y), remain, font=fit_font(remain, inner, pt(FOOTNOTE), SMALL_WEIGHT),
                  fill=LABEL, anchor="ms")
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
        draw.text((text_left, cy + px(27.5)), remain, font=fit_font(remain, width, pt(FOOTNOTE), SMALL_WEIGHT),
                  fill=LABEL, anchor="ls")
    return image
