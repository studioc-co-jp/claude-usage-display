"""経過の目印つきの横棒の画面（``--theme pace``）。5.2 インチで「5時間」と「週次」の 2 つだけを出す（2026-11-03）。

ユーザーが Fable を使っていないので 2 項目にし、見せ方を見本の 3 案から選んだ（「案 2」。``docs/handover.md`` §4-24）。

- 上下 2 段に、Apple の Gauges の直線の容量ゲージ（値の位置まで塗る）を太い横棒で置く。2 本は同じ幅・同じ左端なので、
  棒の端の位置で 2 つを比べられる
- 棒の上の白い目印は、枠の時間（5時間は 5 時間、週次は 7 日）のうちどれだけ過ぎたか。塗った部分が目印より右なら、
  時間の進みより速く使っている。名前の右に「経過 78%」も出す
- 数字は右上に大きく（% は小さく灰色）。下の行は、左にリセットの日時、右に残り時間
- 寸法は 5.2 インチ（1280×720）のピクセルで持ち、ほかの大きさでは高さの比で縮める。見出しはゲージ型の画面と同じ
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from . import gauge
from .gauge import BACKGROUND, CARD, DARK_TRACK_MIX, LABEL, ORANGE, SECONDARY, _mix, rounded, tint
from .render import font
from .usage import Meter, Snapshot

HEIGHT = 720  # 寸法を決めた画面の高さ
WINDOWS = (timedelta(hours=5), timedelta(days=7))  # 5時間と週次の枠の長さ（API の five_hour・seven_day）
MARGIN = 60          # 左右の余白
ROWS = (100, 410)    # 2 段の上端
DIVIDER = 395        # 2 段の間の線
NAME = (66, 52)      # 名前の基準線（段の上端から）・大きさ
PACE_SIZE = 32       # 名前の右の「経過 N%」の大きさ
PACE_GAP = 24        # 名前と「経過」の間
NUMBER = (118, 140)  # 数字の基準線・大きさ
UNIT = 50            # 「%」の大きさ（2026-11-03、70 から、ユーザーの指示で小さくした）
UNIT_GAP = 4         # 数字と「%」の間
BAR = (150, 196)     # 棒の上端と下端
MARK = (8, 14)       # 経過の目印の幅と、棒の上下にはみ出す長さ
LINE = (262, 36)     # 下の行の基準線・大きさ


def elapsed(meter: Meter, window: timedelta, now: datetime) -> float | None:
    """枠の時間のうち過ぎた割合（0〜1）。リセットの時刻が無ければ None。"""
    if meter.resets_at is None:
        return None
    return max(0.0, min(1.0, 1 - (meter.resets_at - now) / window))


def _reset_text(when: str) -> str:
    return when if when.startswith("リセット") else f"リセット {when}"  # 「リセット済み」はそのまま


def render(snapshot: Snapshot | None, now: datetime, status: str | None = None,
           labels: tuple[str, ...] = ("5時間", "週次", "Fable週次"),
           size: tuple[int, int] = (1280, 720), icons: dict[str, Image.Image] | None = None) -> Image.Image:
    """``snapshot`` の先頭の 2 つ（5時間・週次）を描く。引数はゲージ型の画面（``gauge.render``）と同じ。"""
    layout = gauge.layout_for(size)
    s = layout.height / HEIGHT
    sized = lambda value: round(value * s)  # noqa: E731
    width = layout.width
    left, right = MARGIN * s, width - MARGIN * s
    meters = snapshot.meters[:2] if snapshot else tuple(Meter(label, None, None) for label in labels[:2])

    shapes = gauge._Shapes(layout)
    marks = []
    for meter, window, top in zip(meters, WINDOWS, ROWS):
        bar_top, bar_bottom = (top + BAR[0]) * s, (top + BAR[1]) * s
        radius = (bar_bottom - bar_top) / 2
        color = None if meter.percent is None else tint(meter.percent)
        track = _mix(color or SECONDARY, BACKGROUND, DARK_TRACK_MIX)  # 値が無いときは灰色の地だけ
        if color == gauge.BLUE:
            color = layout.blue
        shapes.rounded_rectangle((left, bar_top, right, bar_bottom), radius, track)
        if meter.percent is not None and meter.percent > 0:
            end = left + (right - left) * min(meter.percent, 100) / 100
            shapes.rounded_rectangle((left, bar_top, max(end, left + 2 * radius), bar_bottom), radius, color)
        fraction = elapsed(meter, window, now)
        marks.append(fraction)
        if fraction is not None:
            half, reach = MARK[0] * s / 2, MARK[1] * s
            x = min(max(left + (right - left) * fraction, left + half), right - half)  # 両端でも棒からはみ出さない
            shapes.rounded_rectangle((x - half, bar_top - reach, x + half, bar_bottom + reach), half, LABEL)
    if status:
        shapes.circle(*gauge._badge(layout, gauge.HEADER_BASELINE), layout.px(7), ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)
    gauge._header(image, draw, layout, gauge.HEADER_BASELINE, "Claude Code", snapshot, status,
                  (icons or {}).get("claude"), layout.stamp)
    draw.line((left, DIVIDER * s, right, DIVIDER * s), fill=CARD, width=max(1, sized(2)))
    for meter, fraction, top in zip(meters, marks, ROWS):
        name_font = font(sized(NAME[1]), 6)
        baseline = (top + NAME[0]) * s
        draw.text((left, baseline), meter.label, font=name_font, fill=LABEL, anchor="ls")
        if fraction is not None:
            draw.text((left + name_font.getlength(meter.label) + PACE_GAP * s, baseline), f"経過 {fraction * 100:.0f}%",
                      font=font(sized(PACE_SIZE), 3), fill=SECONDARY, anchor="ls")
        baseline = (top + NUMBER[0]) * s
        if meter.percent is None:
            draw.text((right, baseline), "--", font=rounded(sized(NUMBER[1])), fill=LABEL, anchor="rs")
        else:
            unit = rounded(sized(UNIT))
            draw.text((right, baseline), "%", font=unit, fill=SECONDARY, anchor="rs")
            draw.text((right - unit.getlength("%") - UNIT_GAP * s, baseline), f"{round(meter.percent)}",
                      font=rounded(sized(NUMBER[1])), fill=LABEL, anchor="rs")
        when, remain = gauge.reset_lines(meter.resets_at, now)
        baseline = (top + LINE[0]) * s
        # リセットと残り時間は、大きさも太さも同じ（2026-11-03、残り時間を W3 にしていたら小さく見えるとユーザーが指摘）
        line_font = font(sized(LINE[1]), 6)
        draw.text((left, baseline), _reset_text(when), font=line_font, fill=LABEL, anchor="ls")
        draw.text((right, baseline), remain, font=line_font, fill=LABEL, anchor="rs")
    return image
