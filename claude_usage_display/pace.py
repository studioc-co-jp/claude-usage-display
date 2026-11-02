"""5時間と週次の 2 つを太い横棒で出す画面（``--theme pace``）。5.2 インチ向けに作った（2026-11-03）。

ユーザーが Fable を使っていないので 2 項目にし、見せ方を見本の 3 案から選んだ（「案 2」。``docs/handover.md`` §4-24）。

- 上下 2 段に、Apple の Gauges の直線の容量ゲージ（値の位置まで塗る）を太い横棒で置く。2 本は同じ幅・同じ左端なので、
  棒の端の位置で 2 つを比べられる
- 数字は右上に（% は小さく灰色）。下の行は、左にリセットの日時、右に残り時間
- 名前の pace は、最初は棒の上に枠の時間の経過の目印（と名前の右に「経過 N%」）を出していたことから。同じ日に、
  ユーザーの指示「時間経過の表記と縦棒は不要」で外した。登録（``--theme pace``）を変えずに使えるよう、名前は残した
- 寸法は 5.2 インチ（1280×720）のピクセルで持ち、ほかの大きさでは高さの比で縮める。見出しはゲージ型の画面と同じ
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image, ImageDraw

from . import gauge
from .gauge import BACKGROUND, CARD, DARK_TRACK_MIX, LABEL, ORANGE, SECONDARY, _mix, rounded, tint
from .render import font
from .usage import Meter, Snapshot

HEIGHT = 720  # 寸法を決めた画面の高さ
MARGIN = 60          # 左右の余白
ROWS = (100, 410)    # 2 段の上端
DIVIDER = 395        # 2 段の間の線
NAME = (66, 52)      # 名前の基準線（段の上端から）・大きさ
# 数字と下の行の大きさは、ユーザーの指示「使用量の数値をもう少し小さくして、その分リセットとあとを大きく」で、
# 数字 140→110・% 50→40・下の行 36→46 にした（2026-11-03。下の行は大きくした分、基準線を 262→270 に下げた）
NUMBER = (118, 110)  # 数字の基準線・大きさ
UNIT = 40            # 「%」の大きさ（同日、70→50 をユーザーの指示で小さくし、数字に合わせて 40 にした）
UNIT_GAP = 4         # 数字と「%」の間
BAR = (150, 196)     # 棒の上端と下端
LINE = (270, 46)     # 下の行の基準線・大きさ
# 見出しの右の時刻の大きさ（3.5 インチの寸法）。となりのこの Mac の状態の画面（monitor_screen の横置き、16）に
# そろえる（2026-11-03 ユーザーの指示。ゲージ型の画面の 3.5 インチの既定は 13 で、並べると小さく見えた）。
# 5.2 インチでは 36 px で、それまでと同じ
STAMP = 16


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
    for meter, top in zip(meters, ROWS):
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
    if status:
        shapes.circle(*gauge._badge(layout, gauge.HEADER_BASELINE), layout.px(7), ORANGE)

    image = shapes.finish()
    draw = ImageDraw.Draw(image)
    gauge._header(image, draw, layout, gauge.HEADER_BASELINE, "Claude Code", snapshot, status,
                  (icons or {}).get("claude"), STAMP)
    draw.line((left, DIVIDER * s, right, DIVIDER * s), fill=CARD, width=max(1, sized(2)))
    for meter, top in zip(meters, ROWS):
        draw.text((left, (top + NAME[0]) * s), meter.label, font=font(sized(NAME[1]), 6), fill=LABEL, anchor="ls")
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
