"""サーバーの状態の画面（monitor コマンド、3.5 インチ。横置き 480×320・縦置き 320×480）。

2×2 に、リングと数字を並べる。見出しに、外形・死活監視の判定を出す。

- リングの色は、いちばん新しい値で変わる。しきい値の 15 ポイント手前からオレンジ、しきい値以上で赤
- サイト・サーバーの異常（``server_monitor.assess`` の ``alerts``。値はしきい値以上が ``datapoints`` 回続いたとき）が
  あれば、画面全体を明るい赤
  （HIG の Red）にする。赤い地では赤の文字が見えないため、アラートの項目を白ではっきり、ほかを薄く出す
- ジョブの障害などは、地を黒のまま、見出しにオレンジで件数を出す
- 横置きは、区画の左にリング、右に名前と大きな数字。縦置きは、名前の下にリング、リングの中に数字
  （どちらもユーザーが見本の画像で選んだ。2026-10-10・2026-10-11）
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .gauge import BACKGROUND, BLUE, CARD, LABEL, ORANGE, RED, SECONDARY, _mix, rounded
from .render import JST, SMALL_WEIGHT, fit_font, font
from .server_monitor import Assessment, MonitorConfig, ServerStatus, warning_tint

SCALE = 4
GREEN = (48, 209, 88)  # HIG の Green（ダーク）
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class _Layout:
    """配置。座標はすべて画面のピクセル。区画の中の位置は区画の左上から測る。"""

    size: tuple[int, int]
    inset: int                                   # 見出しの左右の余白
    title_baseline: float                        # 名前と時刻の行
    pill: tuple[int, int, int, int]              # 赤の状態でアラートを出す白い帯
    status_baseline: float                       # 監視の状態の文言の行（帯の中の文字もこの行）
    dot_y: float                                 # 監視の状態の点の中心
    status_size: int                             # 監視の状態の文言の大きさ
    alert_size: int                              # 帯の中のアラートの大きさ
    dot_radius: float                            # 監視の状態の点の半径
    # アラートが 2 件以上のとき、帯を 2 行にする場合の帯と各行の位置（None なら 1 行に「ほか N 件」まで詰める）
    tall_pill: tuple[int, int, int, int] | None
    tall_baselines: tuple[float, float] | None
    cells: tuple[tuple[int, int], ...]           # 2×2 の各区画の左上
    ring: tuple[float, float, float, float]      # 中心 x・中心 y・半径・太さ
    label: tuple[float, float, str, int]         # 名前の位置・anchor・大きさ
    number: tuple[float, float, int, int, bool]  # 数字の位置・大きさ・% の大きさ・中央にそろえるか
    threshold: tuple[float, float, str, int]     # しきい値の位置・anchor・大きさ
    dividers: tuple[tuple[float, float, float, float], ...]


LANDSCAPE = _Layout(
    size=(480, 320), inset=20, title_baseline=25, pill=(116, 6, 364, 32), status_baseline=25, dot_y=20,
    status_size=13, alert_size=15, dot_radius=4.5, tall_pill=None, tall_baselines=None,
    cells=((20, 44), (250, 44), (20, 182), (250, 182)), ring=(52, 68, 48, 11), label=(118, 50, "ls", 15),
    number=(118, 98, 40, 18, False), threshold=(118, 120, "ls", 12), dividers=((240, 56, 240, 304), (20, 182, 460, 182)))
PORTRAIT = _Layout(
    size=(320, 480), inset=16, title_baseline=26, pill=(16, 38, 304, 70), status_baseline=60, dot_y=53.5,
    # 監視の状態は、実機を見たユーザーの指示で大きくした（2026-10-11。文言 13→18、帯の中 15→18）。
    # 1 行に「ほか N 件」まで詰めると 12 ピクセルまで縮むので、アラートが 2 件以上なら帯を 2 行にする
    status_size=18, alert_size=18, dot_radius=6, tall_pill=(16, 35, 304, 87), tall_baselines=(57, 79),
    # 名前・しきい値・リングは、実機を見たユーザーの指示で大きくした（2026-10-11。名前 15→18、しきい値 12→14、
    # リングの半径 46→56・太さ 10→12、数字 30→34）
    cells=((0, 80), (160, 80), (0, 280), (160, 280)), ring=(80, 100, 56, 12), label=(80, 28, "ms", 18),
    number=(80, 112, 34, 16, True), threshold=(80, 184, "ms", 14), dividers=((160, 92, 160, 466), (16, 280, 304, 280)))


class _Shapes:
    def __init__(self, size, background):
        self.size = size
        self.image = Image.new("RGB", (size[0] * SCALE, size[1] * SCALE), background)
        self.draw = ImageDraw.Draw(self.image)

    def _box(self, x0, y0, x1, y1):
        return x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE

    def circle(self, cx, cy, r, fill):
        self.draw.ellipse(self._box(cx - r, cy - r, cx + r, cy + r), fill=fill)

    def pill(self, box, fill, radius: float | None = None):
        radius = (box[3] - box[1]) / 2 if radius is None else radius
        self.draw.rounded_rectangle(self._box(*box), radius * SCALE, fill=fill)

    def ring(self, cx, cy, radius, ring_width, percent: float | None, color, track):
        box = self._box(cx - radius, cy - radius, cx + radius, cy + radius)
        width = round(ring_width * SCALE)
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


def _alert_text(assessment: Assessment) -> str:
    rest = len(assessment.alerts) - 1
    return assessment.alerts[0] + (f"　ほか {rest} 件" if rest else "")


def render(status: ServerStatus | None, assessment: Assessment | None, config: MonitorConfig,
           fetch_error: str | None = None, portrait: bool = False) -> Image.Image:
    """``status`` は最後に取れた値（まだ無ければ None）。``fetch_error`` は直近の取得の失敗の説明。"""
    layout = PORTRAIT if portrait else LANDSCAPE
    width = layout.size[0]
    red = assessment is not None and assessment.red
    background = RED if red else BACKGROUND
    faint = _mix(WHITE, RED, 0.45) if red else SECONDARY
    divider = _mix(WHITE, RED, 0.22) if red else CARD
    alerting = assessment.alerting_metrics if assessment else frozenset()
    metrics = status.metrics if status else ()
    specs = [m.spec for m in metrics] or list(config.metrics)
    ring_x, ring_y, radius, ring_width = layout.ring

    shapes = _Shapes(layout.size, background)
    for index, spec in enumerate(specs):
        x, y = layout.cells[index]
        value = metrics[index].value if metrics else None
        if red:
            color = WHITE if spec.label in alerting else faint
            track = _mix(WHITE, RED, 0.22)
        else:
            tint = "normal" if value is None else warning_tint(value, spec.threshold)
            color = {"normal": BLUE, "warning": ORANGE, "critical": RED}[tint]
            track = _mix(SECONDARY if value is None else color, BACKGROUND, 0.22)
        shapes.ring(x + ring_x, y + ring_y, radius, ring_width, value, color, track)
    # 監視の状態: 赤の状態は白い帯にアラート、それ以外は点と短い文言
    pill_width = layout.pill[2] - layout.pill[0]
    message = message_font = message_left = None
    warn = False
    two_lines = red and layout.tall_pill is not None and len(assessment.alerts) > 1
    if two_lines:
        shapes.pill(layout.tall_pill, WHITE, radius=16)
    elif red:
        shapes.pill(layout.pill, WHITE)
    else:
        message = fetch_error or (assessment.warnings[0] if assessment and assessment.warnings else None)
        warn = message is not None
        if message is None and status and status.monitor is not None:
            message = "監視 正常"
        if message:
            dot_space = layout.dot_radius * 2 + 5
            message_font = fit_font(message, pill_width - 20, layout.status_size, SMALL_WEIGHT)
            message_left = width / 2 - (message_font.getlength(message) + dot_space) / 2 + dot_space
            shapes.circle(message_left - layout.dot_radius - 5, layout.dot_y, layout.dot_radius,
                          ORANGE if warn else GREEN)
    image = shapes.finish()
    draw = ImageDraw.Draw(image)

    # 見出し
    ink = WHITE if red else LABEL
    draw.text((layout.inset, layout.title_baseline), config.title, font=font(15, 6), fill=ink, anchor="ls")
    if status:
        stamp = f"{status.fetched_at.astimezone(JST):%H:%M} " + ("時点" if fetch_error else "更新")
        draw.text((width - layout.inset, layout.title_baseline), stamp, font=font(13, SMALL_WEIGHT), fill=ink,
                  anchor="rs")
    if two_lines:
        first, second = layout.tall_baselines
        text = assessment.alerts[0]
        draw.text((width / 2, first), text, font=fit_font(text, pill_width - 24, layout.alert_size, 6), fill=RED,
                  anchor="ms")
        draw.text((width / 2, second), f"ほか {len(assessment.alerts) - 1} 件", font=font(15, 6), fill=RED,
                  anchor="ms")
    elif red:
        text = _alert_text(assessment)
        draw.text((width / 2, layout.status_baseline - 1 if not portrait else layout.status_baseline + 1), text,
                  font=fit_font(text, pill_width - 24, layout.alert_size, 6), fill=RED, anchor="ms")
    elif message:
        draw.text((message_left, layout.status_baseline), message, font=message_font,
                  fill=ORANGE if warn else LABEL, anchor="ls")

    # 2×2
    for line in layout.dividers:
        draw.line(line, fill=divider, width=1)
    label_x, label_y, label_anchor, label_size = layout.label
    number_x, number_y, number_size, unit_size, centered = layout.number
    threshold_x, threshold_y, threshold_anchor, threshold_size = layout.threshold
    for index, spec in enumerate(specs):
        x, y = layout.cells[index]
        value = metrics[index].value if metrics else None
        strong = WHITE if (not red or spec.label in alerting) else faint
        draw.text((x + label_x, y + label_y), spec.label, font=font(label_size, 6), fill=strong, anchor=label_anchor)
        number = "--" if value is None else f"{value:.0f}"
        number_font, unit_font = rounded(number_size), rounded(unit_size)
        number_width = draw.textlength(number, font=number_font)
        gap = 1 if centered else 2
        unit_width = 0 if value is None else draw.textlength("%", font=unit_font) + gap
        left = x + number_x - ((number_width + unit_width) / 2 if centered else 0)
        draw.text((left, y + number_y), number, font=number_font, fill=strong, anchor="ls")
        if value is not None:
            draw.text((left + number_width + gap, y + number_y), "%", font=unit_font, fill=faint, anchor="ls")
        draw.text((x + threshold_x, y + threshold_y), f"しきい値 {spec.threshold:g}%",
                  font=font(threshold_size, SMALL_WEIGHT), fill=faint, anchor=threshold_anchor)
    return image
