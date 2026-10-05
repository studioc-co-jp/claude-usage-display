"""ゲージ型の画面（既定）。

Apple のウィジェット（バッテリー）とアクティビティのリングを手本にした。上端に見出しを置き、
その下にカード 3 枚を並べて、カードごとに円形のゲージ・使用率・リセット時刻を出す。

- 色は Human Interface Guidelines（Color）のダークモードのシステムカラー（2025-06-09 更新の値）
- 文字の大きさは HIG（Typography）の iOS 既定の文字スタイルの pt を、そのままピクセルで使う。
  このパネル（3.5 インチ・480×320）は iPhone 3GS（3.5 インチ・480×320・163 ppi）と同じ大きさなので、
  iPhone で見る文字とほぼ同じ大きさになる
- 図形は SCALE 倍で描いてから縮め、縁を滑らかにする。文字は縮めるとかすれるため、縮めた後に等倍で書く
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .render import CRITICAL_AT, HEIGHT, JST, WARNING_AT, WEEKDAYS, WIDTH, fit_font, font, format_remaining
from .usage import Meter, Snapshot

SCALE = 4

BACKGROUND = (0, 0, 0)
# HIG の Gray (6) は (28, 28, 30) だが、RGB565（赤・青 5 ビット、緑 6 ビット）では (24, 28, 24) になり緑に寄る。
# RGB565 でそのまま表せる無彩色のうち近いもの（液晶で黒地との差が見えやすい明るい側）を使う
CARD = (33, 32, 33)
LABEL = (255, 255, 255)
SECONDARY = (142, 142, 147)  # Gray
TERTIARY = (99, 99, 102)     # Gray (2)
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
def content_rows() -> tuple[float, float, float, float, float, float]:
    """カードの中身の各行の位置（中身の上端から測る）と、中身の高さ。

    上端は見出しの字の上端、下端は残り時間の字の下端で、どちらもフォントの実寸で測る。
    """
    ascent = -font(SUBHEAD, 6).getbbox("時", anchor="ls")[1]
    descent = font(FOOTNOTE, 3).getbbox("あと", anchor="ls")[3]
    label = ascent
    ring_center = label + 16 + RING_RADIUS
    caption = ring_center + RING_RADIUS + 28
    when = caption + 22
    remain = when + 27  # 日時との間を空け、残り時間を別の情報として読ませる
    return label, ring_center, caption, when, remain, remain + descent


def card_box(index: int) -> tuple[float, float, float, float]:
    left = MARGIN + index * (CARD_WIDTH + CARD_GAP)
    return left, CARD_TOP, left + CARD_WIDTH, HEIGHT - MARGIN


class _Shapes:
    """図形を SCALE 倍で描く下書き。"""

    def __init__(self):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)

    def _box(self, x0, y0, x1, y1):
        return x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE

    def rounded_rectangle(self, box, radius, fill):
        self.draw.rounded_rectangle(self._box(*box), radius * SCALE, fill=fill)

    def circle(self, cx, cy, r, fill):
        self.draw.ellipse(self._box(cx - r, cy - r, cx + r, cy + r), fill=fill)

    def ring(self, cx, cy, percent: float | None):
        """12 時の位置から時計回りに伸びる、端の丸いリング。"""
        color = BLUE if percent is None else tint(percent)
        track = _mix(SECONDARY if percent is None else color, CARD, TRACK_MIX)
        box = self._box(cx - RING_RADIUS, cy - RING_RADIUS, cx + RING_RADIUS, cy + RING_RADIUS)
        width = RING_WIDTH * SCALE
        self.draw.ellipse(box, outline=track, width=width)
        if percent is None or percent <= 0:
            return
        sweep = 360 * min(percent, 100) / 100
        self.draw.arc(box, -90, -90 + sweep, fill=color, width=width)
        middle = RING_RADIUS - RING_WIDTH / 2
        for angle in (-90, -90 + sweep):
            a = math.radians(angle)
            self.circle(cx + middle * math.cos(a), cy + middle * math.sin(a), RING_WIDTH / 2, color)

    def finish(self) -> Image.Image:
        return self.image.resize((WIDTH, HEIGHT), Image.LANCZOS)


def _value(draw: ImageDraw.ImageDraw, cx: float, baseline: float, percent: float | None) -> None:
    """「26」を大きく、「%」を小さく灰色で、ベースラインをそろえて中央に書く。"""
    number = "--" if percent is None else f"{round(percent)}"
    number_font, unit_font = rounded(TITLE1), rounded(SUBHEAD)
    number_width = draw.textlength(number, font=number_font)
    unit_width = 0 if percent is None else draw.textlength("%", font=unit_font) + 1
    left = cx - (number_width + unit_width) / 2
    draw.text((left, baseline), number, font=number_font, fill=LABEL, anchor="ls")
    if percent is not None:
        draw.text((left + number_width + 1, baseline), "%", font=unit_font, fill=SECONDARY, anchor="ls")


def render(snapshot: Snapshot | None, now: datetime, status: str | None = None,
           labels: tuple[str, ...] = ("5時間", "週次", "Fable週次")) -> Image.Image:
    """``status`` は取得に失敗したときの短い説明。前回の値を残したまま、見出しの位置に出す。"""
    meters = snapshot.meters[:3] if snapshot else tuple(Meter(label, None, None) for label in labels)
    label_y, ring_y, caption_y, when_y, remain_y, content_height = content_rows()

    shapes = _Shapes()
    centers = []
    for index, meter in enumerate(meters):
        left, top, right, bottom = card_box(index)
        shapes.rounded_rectangle((left, top, right, bottom), CARD_RADIUS, CARD)
        origin = top + (bottom - top - content_height) / 2
        cx = (left + right) / 2
        percent = None if meter.percent is None else max(0.0, min(100.0, meter.percent))
        shapes.ring(cx, origin + ring_y, percent)
        centers.append((cx, origin))
    badge = (HEADER_INSET + 7, HEADER_BASELINE - 5.5)
    if status:
        shapes.circle(*badge, 7, ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)

    small = font(FOOTNOTE, 3)
    fetched = f"{snapshot.fetched_at.astimezone(JST):%H:%M}" if snapshot else ""
    if status:
        when = f"{fetched} 時点" if snapshot else ""
        draw.text((WIDTH - HEADER_INSET, HEADER_BASELINE), when, font=small, fill=SECONDARY, anchor="rs")
        draw.text((badge[0], badge[1] + 4.5), "!", font=rounded(CAPTION1, "Bold"), fill=BACKGROUND, anchor="ms")
        message_left = HEADER_INSET + 20
        reserved = small.getlength(when) + STATUS_GAP if when else 0
        draw.text((message_left, HEADER_BASELINE), status,
                  font=fit_font(status, WIDTH - HEADER_INSET - message_left - reserved, FOOTNOTE),
                  fill=ORANGE, anchor="ls")
    else:
        draw.text((HEADER_INSET, HEADER_BASELINE), "Claude Code", font=font(SUBHEAD, 6), fill=LABEL, anchor="ls")
        if snapshot:
            draw.text((WIDTH - HEADER_INSET, HEADER_BASELINE), f"{fetched} 更新", font=small, fill=SECONDARY,
                      anchor="rs")

    inner = CARD_WIDTH - CARD_PADDING * 2
    for (cx, origin), meter in zip(centers, meters):
        draw.text((cx, origin + label_y), meter.label, font=fit_font(meter.label, inner, SUBHEAD, 6), fill=LABEL,
                  anchor="ms")
        percent = None if meter.percent is None else max(0.0, meter.percent)
        _value(draw, cx, origin + ring_y + 10, percent)
        when, remain = reset_lines(meter.resets_at, now)
        draw.text((cx, origin + caption_y), "リセット", font=font(CAPTION1, 3), fill=TERTIARY, anchor="ms")
        draw.text((cx, origin + when_y), when, font=fit_font(when, inner, SUBHEAD, 6), fill=LABEL, anchor="ms")
        draw.text((cx, origin + remain_y), remain, font=fit_font(remain, inner, FOOTNOTE), fill=SECONDARY,
                  anchor="ms")
    return image
