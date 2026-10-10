"""サーバーの状態の画面（monitor コマンド、3.5 インチ・480×320）。

2×2 に、小さなリングと大きな数字を並べる。見出しの中央に、外形・死活監視の判定を出す。

- リングの色は値で変わる。しきい値の 15 ポイント手前からオレンジ、しきい値以上で赤
- サイト・サーバーの異常（``server_monitor.assess`` の ``alerts``）があれば、画面全体を明るい赤
  （HIG の Red）にする。赤い地では赤の文字が見えないため、アラートの項目を白ではっきり、ほかを薄く出す
- ジョブの障害などは、地を黒のまま、見出しにオレンジで件数を出す
"""

from __future__ import annotations

import math
from datetime import datetime

from PIL import Image, ImageDraw

from .gauge import BACKGROUND, BLUE, CARD, LABEL, ORANGE, RED, SECONDARY, _mix, rounded
from .render import HEIGHT, JST, SMALL_WEIGHT, WIDTH, fit_font, font
from .server_monitor import Assessment, MonitorConfig, ServerStatus, warning_tint

SCALE = 4
GREEN = (48, 209, 88)  # HIG の Green（ダーク）
WHITE = (255, 255, 255)
CELLS = ((20, 44), (250, 44), (20, 182), (250, 182))  # 2×2 の各区画の左上
RING_RADIUS, RING_WIDTH = 48, 11
PILL = (116, 6, WIDTH - 116, 32)  # 赤の状態で、見出しの中央に置く白い帯（左の名前と右の時刻に重ねない）


class _Shapes:
    def __init__(self, background):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), background)
        self.draw = ImageDraw.Draw(self.image)

    def _box(self, x0, y0, x1, y1):
        return x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE

    def circle(self, cx, cy, r, fill):
        self.draw.ellipse(self._box(cx - r, cy - r, cx + r, cy + r), fill=fill)

    def pill(self, box, fill):
        self.draw.rounded_rectangle(self._box(*box), (box[3] - box[1]) / 2 * SCALE, fill=fill)

    def ring(self, cx, cy, percent: float | None, color, track):
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


def _alert_text(assessment: Assessment) -> str:
    rest = len(assessment.alerts) - 1
    return assessment.alerts[0] + (f"　ほか {rest} 件" if rest else "")


def render(status: ServerStatus | None, assessment: Assessment | None, config: MonitorConfig,
           fetch_error: str | None = None) -> Image.Image:
    """``status`` は最後に取れた値（まだ無ければ None）。``fetch_error`` は直近の取得の失敗の説明。"""
    red = assessment is not None and assessment.red
    background = RED if red else BACKGROUND
    faint = _mix(WHITE, RED, 0.45) if red else SECONDARY
    divider = _mix(WHITE, RED, 0.22) if red else CARD
    alerting = assessment.alerting_metrics if assessment else frozenset()
    metrics = status.metrics if status else ()
    specs = [m.spec for m in metrics] or list(config.metrics)

    shapes = _Shapes(background)
    for index, spec in enumerate(specs):
        x, y = CELLS[index]
        metric = metrics[index] if metrics else None
        value = None if metric is None else metric.value
        if red:
            color = WHITE if spec.label in alerting else faint
            track = _mix(WHITE, RED, 0.22)
        else:
            tint = "normal" if value is None else warning_tint(value, spec.threshold)
            color = {"normal": BLUE, "warning": ORANGE, "critical": RED}[tint]
            track = _mix(SECONDARY if value is None else color, BACKGROUND, 0.22)
        shapes.ring(x + 52, y + 68, value, color, track)
    # 見出しの中央: 赤の状態は白い帯にアラート、それ以外は点と短い文言
    message = message_font = message_left = None
    if red:
        shapes.pill(PILL, WHITE)
    else:
        message = fetch_error or (assessment.warnings[0] if assessment and assessment.warnings else None)
        warn = message is not None
        if message is None and status and status.monitor is not None:
            message = "監視 正常"
        if message:
            message_font = fit_font(message, PILL[2] - PILL[0] - 20, 13, SMALL_WEIGHT)
            message_left = WIDTH / 2 - (message_font.getlength(message) + 14) / 2 + 14
            shapes.circle(message_left - 9.5, 20, 4.5, ORANGE if warn else GREEN)
    image = shapes.finish()
    draw = ImageDraw.Draw(image)

    # 見出し
    ink = WHITE if red else LABEL
    draw.text((20, 25), config.title, font=font(15, 6), fill=ink, anchor="ls")
    if status:
        stamp = f"{status.fetched_at.astimezone(JST):%H:%M} " + ("時点" if fetch_error else "更新")
        draw.text((WIDTH - 20, 25), stamp, font=font(13, SMALL_WEIGHT), fill=ink, anchor="rs")
    if red:
        text = _alert_text(assessment)
        draw.text((WIDTH / 2, 24), text, font=fit_font(text, PILL[2] - PILL[0] - 24, 15, 6), fill=RED, anchor="ms")
    elif message:
        warn = message != "監視 正常"
        draw.text((message_left, 25), message, font=message_font, fill=ORANGE if warn else LABEL, anchor="ls")

    # 2×2
    draw.line((WIDTH / 2, 56, WIDTH / 2, HEIGHT - 16), fill=divider, width=1)
    draw.line((20, 182, WIDTH - 20, 182), fill=divider, width=1)
    for index, spec in enumerate(specs):
        x, y = CELLS[index]
        metric = metrics[index] if metrics else None
        value = None if metric is None else metric.value
        strong = WHITE if (not red or spec.label in alerting) else faint
        draw.text((x + 118, y + 50), spec.label, font=font(15, 6), fill=strong, anchor="ls")
        number = "--" if value is None else f"{value:.0f}"
        number_font = rounded(40)
        draw.text((x + 118, y + 98), number, font=number_font, fill=strong, anchor="ls")
        if value is not None:
            draw.text((x + 118 + draw.textlength(number, font=number_font) + 2, y + 98), "%", font=rounded(18),
                      fill=faint, anchor="ls")
        draw.text((x + 118, y + 120), f"しきい値 {spec.threshold:g}%", font=font(12, SMALL_WEIGHT), fill=faint,
                  anchor="ls")
    return image
