"""5時間と週次の 2 つを太い横棒で出す画面（``--theme pace``）。5.2 インチ向けに作った（2026-11-03）。

ユーザーが Fable を使っていないので 2 項目にし、見せ方を見本の 3 案から選んだ（「案 2」。``docs/handover.md`` §4-24）。

- 上下 2 段に、Apple の Gauges の直線の容量ゲージ（値の位置まで塗る）を太い横棒で置く。2 本は同じ幅・同じ左端なので、
  棒の端の位置で 2 つを比べられる
- 名前は棒の真上の左、数字は右上に（% は小さく灰色）。名前と数字は同じ基準線に載せる。下の行は、左にリセットの日時、
  右に残り時間
- 名前の pace は、最初は棒の上に枠の時間の経過の目印（と名前の右に「経過 N%」）を出していたことから。同じ日に、
  ユーザーの指示「時間経過の表記と縦棒は不要」で外した。登録（``--theme pace``）を変えずに使えるよう、名前は残した
- 寸法は 5.2 インチ（1280×720）のピクセルで持ち、ほかの大きさでは高さの比で縮める。見出しはゲージ型の画面と同じ
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image, ImageDraw

from . import gauge
from .gauge import BACKGROUND, DARK_TRACK_MIX, LABEL, ORANGE, SECONDARY, _mix, paste_mark, rounded, tint
from .render import font
from .usage import Meter, Snapshot

HEIGHT = 720  # 寸法を決めた画面の高さ
MARGIN = 60          # 左右の余白
# 2 段の間の罫線を消し、段の間と下の余白を詰めた分で、名前 52→56・数字 110→120・% 40→44・棒の太さ 46→56・
# 下の行 46→50 にした（2026-11-03、ユーザーの指示「3.5 モニターの罫線は消してその分項目を大きくして」）。
# それまでの経緯: 数字 140→110・% 50→40・下の行 36→46（同日、「使用量の数値をもう少し小さくして、その分リセットと
# あとを大きく」）、% 70→50（同日、「% はもう少し小さく」）
# 5時間と週次の間を広げた（約 15→27 px（3.5 インチ）。同日、ユーザーの指示「5時間と週次を隙間を空けたい」）。
# 1 段目を 84→76 に上げ、2 段目を 398→412 に下げ、下の行を 290→284 に上げて画面の下に収めた
ROWS = (76, 412)     # 2 段の上端
# 名前は数字と同じ基準線に載せ、棒の真上に置く（2026-11-04、ユーザーの指示「5時間・週次のテキストをバーの真上に」。
# 見本の 2 案から選んだ。70→122。3.5 インチで、名前と棒の間は 35→12 px で、棒と下の行の間（14〜15 px）とほぼ同じ）
NAME = (122, 56)     # 名前の基準線（段の上端から）・大きさ
NUMBER = (122, 120)  # 数字の基準線・大きさ
UNIT = 44            # 「%」の大きさ
UNIT_GAP = 4         # 数字と「%」の間
BAR = (156, 212)     # 棒の上端と下端
LINE = (284, 45)     # 下の行の基準線・大きさ（収まらなければ LINE_MIN まで縮める。2026-11-04、ユーザーの指示「少しだけ小さく」で 50→45。3.5 インチで 22→20 px）
LINE_MIN = 36
LINE_GAP = 32        # 下の行の、リセットと残り時間の間に残す幅
RESET_MARK = 1.0     # リセットの記号の一辺（下の行の字の大きさに対する比）
RESET_GAP = 0.3      # 記号と時刻の間（同じく比）
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
    # 下の行（リセットと残り時間）は、2 段とも左右の間に LINE_GAP を残して収まる大きさにそろえる。寸法を高さの比で
    # 縮めるので、横の狭い 3.5 インチ（3:2）では 50 のままだと週次の日時と残り時間がくっついた（2026-11-03）。
    # アイコンのフォルダに reset.png があれば、「リセット」の文字の代わりにその記号を時刻の左に出す（2026-11-04、
    # ユーザーの指示。「リセット済み」は文字のまま）
    mark = (icons or {}).get("reset")
    lines = []
    for when, remain in (gauge.reset_lines(m.resets_at, now) for m in meters):
        with_mark = mark is not None and not when.startswith("リセット")
        lines.append((with_mark, when if with_mark else _reset_text(when), remain))

    def lead(size: int, with_mark: bool) -> float:
        return size * (RESET_MARK + RESET_GAP) if with_mark else 0  # 記号とその右の間の幅

    line_size = sized(LINE[1])
    while line_size > sized(LINE_MIN) and any(
            lead(line_size, m) + font(line_size, 6).getlength(a) + font(line_size, 6).getlength(b)
            > right - left - LINE_GAP * s for m, a, b in lines):
        line_size -= 1
    line_font = font(line_size, 6)
    for meter, (with_mark, reset_text, remain), top in zip(meters, lines, ROWS):
        draw.text((left, (top + NAME[0]) * s), meter.label, font=font(sized(NAME[1]), 6), fill=LABEL, anchor="ls")
        baseline = (top + NUMBER[0]) * s
        if meter.percent is None:
            draw.text((right, baseline), "--", font=rounded(sized(NUMBER[1])), fill=LABEL, anchor="rs")
        else:
            unit = rounded(sized(UNIT))
            draw.text((right, baseline), "%", font=unit, fill=SECONDARY, anchor="rs")
            draw.text((right - unit.getlength("%") - UNIT_GAP * s, baseline), f"{round(meter.percent)}",
                      font=rounded(sized(NUMBER[1])), fill=LABEL, anchor="rs")
        baseline = (top + LINE[0]) * s
        # リセットと残り時間は、大きさも太さも同じ（2026-11-03、残り時間を W3 にしていたら小さく見えるとユーザーが指摘）
        if with_mark:  # 記号の縦の中心を、数字の字の高さの中ほどにそろえる
            paste_mark(image, mark, left, baseline - line_size * 0.36, round(line_size * RESET_MARK))
        draw.text((left + lead(line_size, with_mark), baseline), reset_text, font=line_font, fill=LABEL, anchor="ls")
        draw.text((right, baseline), remain, font=line_font, fill=LABEL, anchor="rs")
    return image
