"""表示画像（480×320、横向き）の描画。

メーター 3 本（5 時間・週次・モデル別週次）を縦に並べ、使用率とリセット時刻を出す。
メーターの塗りは深刻度（通常 → 注意 → 上限間近）で色を変え、塗っていない部分は
同じ色を背景へ寄せた暗い色にする。数値と文字は色ではなく白・灰で書く。
"""

from __future__ import annotations

import os
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .usage import Meter, Snapshot

WIDTH, HEIGHT = 480, 320
JST = timezone(timedelta(hours=9))
WEEKDAYS = "月火水木金土日"

SURFACE = (0x1A, 0x1A, 0x19)
INK = (0xFF, 0xFF, 0xFF)
INK_SECONDARY = (0xC3, 0xC2, 0xB7)
INK_MUTED = (0x89, 0x87, 0x81)
ACCENT = (0x39, 0x87, 0xE5)
WARNING = (0xFA, 0xB2, 0x19)
CRITICAL = (0xD0, 0x3B, 0x3B)
TRACK_MIX = 0.28  # 塗っていない部分は、塗りの色を背景へ 72% 寄せる

WARNING_AT = 70
CRITICAL_AT = 90

MARGIN_X = 16
ROW_TOP = 8
ROW_HEIGHT = 94
BAR_HEIGHT = 16
BAR_RADIUS = 4
STATUS_GAP = 12  # 下端の行で、左の理由と右の時刻のあいだに空ける幅
MIN_FONT_SIZE = 10
# ヒラギノ角ゴシック W3 は 12・13 ピクセルで、ヒンティングにより「4」の横棒が消える
# （Pillow 12.3.0・FreeType 2.14.3。W4 は 10〜13 ピクセルで崩れない）。13 ピクセル以下になりうる文字は W4 で書く
SMALL_WEIGHT = 4

FONT_DIR = "/System/Library/Fonts"


@lru_cache(maxsize=None)
def _font_path(weight: int) -> str | None:
    """ヒラギノ角ゴシックのファイルを探す（ファイル名は NFD で保存されているため正規化して比べる）。"""
    wanted = f"ヒラギノ角ゴシック W{weight}.ttc"
    try:
        names = os.listdir(FONT_DIR)
    except OSError:
        return None
    for name in names:
        if unicodedata.normalize("NFC", name) == wanted:
            return os.path.join(FONT_DIR, name)
    return None


@lru_cache(maxsize=None)
def font(size: int, weight: int = 3) -> ImageFont.FreeTypeFont:
    path = _font_path(weight)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def fit_font(text: str, max_width: float, size: int, weight: int = 3) -> ImageFont.FreeTypeFont:
    """``text`` が ``max_width`` に収まるまで文字を小さくする（``MIN_FONT_SIZE`` で止める）。"""
    while size > MIN_FONT_SIZE and font(size, weight).getlength(text) > max_width:
        size -= 1
    return font(size, weight)


def severity_color(percent: float) -> tuple[int, int, int]:
    if percent >= CRITICAL_AT:
        return CRITICAL
    if percent >= WARNING_AT:
        return WARNING
    return ACCENT


def _mix(color, base, ratio: float) -> tuple[int, int, int]:
    return tuple(round(c * ratio + b * (1 - ratio)) for c, b in zip(color, base))


def format_remaining(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"あと{days}日{hours}時間"
    if hours:
        return f"あと{hours}時間{minutes:02d}分"
    return f"あと{minutes}分"


def format_reset(resets_at: datetime | None, now: datetime) -> str:
    if resets_at is None:
        return "リセット時刻なし"
    if resets_at <= now:
        return "リセット済み（次の取得で更新）"
    local = resets_at.astimezone(JST)
    if resets_at - now < timedelta(hours=24) and local.date() == now.astimezone(JST).date():
        when = local.strftime("%H:%M")
    else:
        when = f"{local.month}/{local.day}({WEEKDAYS[local.weekday()]}) {local:%H:%M}"
    return f"リセット {when}（{format_remaining(resets_at - now)}）"


def _draw_meter(draw: ImageDraw.ImageDraw, top: int, meter: Meter, now: datetime) -> None:
    right = WIDTH - MARGIN_X
    draw.text((MARGIN_X, top + 26), meter.label, font=font(22, 6), fill=INK, anchor="ls")
    value = "—" if meter.percent is None else f"{round(meter.percent)}%"
    draw.text((right, top + 30), value, font=font(30, 6), fill=INK, anchor="rs")

    bar_top = top + 40
    bar = (MARGIN_X, bar_top, right, bar_top + BAR_HEIGHT)
    if meter.percent is None:
        draw.rounded_rectangle(bar, BAR_RADIUS, fill=_mix(INK_MUTED, SURFACE, TRACK_MIX))
    else:
        percent = max(0.0, min(100.0, meter.percent))
        color = severity_color(percent)
        draw.rounded_rectangle(bar, BAR_RADIUS, fill=_mix(color, SURFACE, TRACK_MIX))
        if percent > 0:
            fill_right = MARGIN_X + max(BAR_RADIUS * 2, round((right - MARGIN_X) * percent / 100))
            draw.rounded_rectangle((MARGIN_X, bar_top, fill_right, bar_top + BAR_HEIGHT), BAR_RADIUS, fill=color)

    draw.text((MARGIN_X, bar_top + BAR_HEIGHT + 22), format_reset(meter.resets_at, now),
              font=font(16, 3), fill=INK_SECONDARY, anchor="ls")


def render(snapshot: Snapshot | None, now: datetime, status: str | None = None,
           labels: tuple[str, ...] = ("5時間", "週次", "Fable週次")) -> Image.Image:
    """``status`` は取得に失敗したときの短い説明。前回の値を残したまま下端に出す。"""
    image = Image.new("RGB", (WIDTH, HEIGHT), SURFACE)
    draw = ImageDraw.Draw(image)

    meters = snapshot.meters if snapshot else tuple(Meter(label, None, None) for label in labels)
    for index, meter in enumerate(meters[:3]):
        _draw_meter(draw, ROW_TOP + index * ROW_HEIGHT, meter, now)

    baseline = HEIGHT - 10
    small = font(14, 3)
    if status:
        # 右に前回の取得時刻、左に理由。理由が長くても右端で切れないよう、収まる大きさまで縮める
        when = f"{snapshot.fetched_at.astimezone(JST):%H:%M} 時点" if snapshot else ""
        reserved = small.getlength(when) + STATUS_GAP if when else 0
        message = f"! {status}"
        draw.text((MARGIN_X, baseline), message,
                  font=fit_font(message, WIDTH - MARGIN_X * 2 - reserved, 14, SMALL_WEIGHT), fill=WARNING, anchor="ls")
        if when:
            draw.text((WIDTH - MARGIN_X, baseline), when, font=small, fill=INK_MUTED, anchor="rs")
    else:
        draw.text((MARGIN_X, baseline), "Claude Code 利用枠", font=small, fill=INK_MUTED, anchor="ls")
        if snapshot:
            draw.text((WIDTH - MARGIN_X, baseline), f"更新 {snapshot.fetched_at.astimezone(JST):%H:%M}",
                      font=small, fill=INK_MUTED, anchor="rs")
    return image


def render_test_pattern(size: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """向きと色の確認用。左上に「左上」、四隅に色、中央に解像度を出す。文字は高さに合わせて大きくする。"""
    width, height = size
    scale = height / HEIGHT
    image = Image.new("RGB", size, SURFACE)
    draw = ImageDraw.Draw(image)
    half_w, half_h = width // 2, height // 2
    for (x, y), color in zip(((0, 0), (half_w, 0), (0, half_h), (half_w, half_h)),
                             ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255))):
        draw.rectangle((x, y, x + half_w - 1, y + half_h - 1), fill=color)
    label = font(round(28 * scale), 6)
    left, base = round(12 * scale), round(36 * scale)
    draw.text((left, base), "左上", font=label, fill=INK, anchor="ls")
    draw.text((half_w + left, base), "緑", font=label, fill=SURFACE, anchor="ls")
    draw.text((left, half_h + base), "青", font=label, fill=INK, anchor="ls")
    draw.text((half_w, half_h), f"{width}×{height}", font=font(round(30 * scale), 6), fill=SURFACE,
              anchor="mm", stroke_width=round(3 * scale), stroke_fill=INK)
    return image
