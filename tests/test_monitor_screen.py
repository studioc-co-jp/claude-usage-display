import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from PIL import Image

from claude_usage_display import monitor_screen as ms
from claude_usage_display import server_monitor as sm
from claude_usage_display.gauge import BACKGROUND, ICON_GAP, ICON_SIZE, ORANGE, RED, SECONDARY
from claude_usage_display.render import SMALL_WEIGHT, font
from tests.test_server_monitor import NOW, config, status


def near(pixel, color, tolerance=12):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color))


def right_ring_left():
    """横置きの右の列のリングの左端（3.5 インチ）。"""
    return ms.LANDSCAPE.cells[1][0] + ms.LANDSCAPE.ring[0] - ms.LANDSCAPE.ring[2]


COUNTERS = (sm.CounterSpec("5xx エラー", "Example/Application", "Http5xx", 5),
            sm.CounterSpec("PHP エラー", "Example/Application", "PhpFatalError", 1))


def status_with_counters(hourly_5xx=(0,) * 24, alarmed_5xx=(False,) * 24, latest_5xx=0):
    """件数の見本（5xx だけ値を変えられる。PHP は 0 件）を付けた状態。"""
    base = status(cfg=config(counters=COUNTERS))
    return sm.ServerStatus(base.metrics, base.monitor, base.fetched_at, (
        sm.CounterValue(COUNTERS[0], tuple(map(float, hourly_5xx)), tuple(alarmed_5xx), float(latest_5xx)),
        sm.CounterValue(COUNTERS[1], (0.0,) * 24, (False,) * 24, 0.0)))


class MonitorScreenTest(unittest.TestCase):
    def render(self, st, error=None):
        cfg = config()
        return ms.render(st, sm.assess(st, cfg, NOW) if st else None, cfg, error)

    def test_normal_is_black(self):
        image = self.render(status())
        self.assertEqual(image.size, (480, 320))
        self.assertEqual(image.getpixel((2, 300)), BACKGROUND)

    def test_alert_turns_the_whole_screen_red_and_the_alerting_ring_white(self):
        image = self.render(status(values=(92, 61, 47, 3)))
        self.assertEqual(image.getpixel((2, 300)), RED)
        # CPU（左上）のリングの 3 時の位置は白、メモリ（右上）は薄い色
        cx, cy, radius, width = ms.LANDSCAPE.ring
        self.assertTrue(near(image.getpixel((round(20 + cx + radius - width / 2), 44 + cy)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel((round(250 + cx + radius - width / 2), 44 + cy)), (255, 255, 255)))

    def test_landscape_puts_the_number_inside_the_ring(self):
        # 2026-10-15 に、数字をリングの右からリングの中へ移した。リングの内側に数字の白があり、右には無い
        image = self.render(status(values=(11, 61, 47, 3)))
        cx, cy, radius, width = ms.LANDSCAPE.ring
        inside = [image.getpixel((20 + x, 44 + y)) for x in range(round(cx - 20), round(cx + 20))
                  for y in range(round(cy - 15), round(cy + 15))]
        self.assertTrue(any(near(p, (255, 255, 255), 40) for p in inside))
        label_x, label_y, _, _ = ms.LANDSCAPE.label
        _, threshold_y, _, threshold_size = ms.LANDSCAPE.threshold
        right = [image.getpixel((20 + x, 44 + y)) for x in range(label_x, 220)
                 for y in range(round(label_y + 2), round(threshold_y - threshold_size))]
        self.assertTrue(all(p == BACKGROUND for p in right))

    def test_landscape_stamp_stays_right_of_the_pill(self):
        # 2026-10-15 に時刻を 13→16 ピクセルにした。帯（アラートの白い地）に時刻がかからない
        start = 480 - ms.LANDSCAPE.inset - font(ms.LANDSCAPE.stamp_size, SMALL_WEIGHT).getlength("00:00 更新")
        self.assertGreater(start, ms.LANDSCAPE.pill[2])

    def test_landscape_threshold_stays_left_of_the_right_column(self):
        # 2026-11-03 に罫線を消した。左の列のしきい値は、右の列のリングの左端から 12 ピクセル以上離れる
        threshold_x, _, _, threshold_size = ms.LANDSCAPE.threshold
        end = ms.LANDSCAPE.cells[0][0] + threshold_x + font(threshold_size, SMALL_WEIGHT).getlength("しきい値 85%")
        self.assertEqual(ms.LANDSCAPE.dividers, ())
        self.assertLessEqual(end, right_ring_left() - 12)

    def test_landscape_detail_stays_gray_and_the_number_has_no_percent_sign(self):
        # 2026-10-27、視認性を上げるため、しきい値を 14→15 ピクセルにし、% を外して数字を 30→38 にした。
        # しきい値を白にもしたが、実機を見たユーザーが「がちゃがちゃする」として灰色に戻した
        image = self.render(status())
        x, y = ms.LANDSCAPE.cells[0]
        threshold_x, threshold_y, _, size = ms.LANDSCAPE.threshold
        band = [image.getpixel((x + px, y + py)) for px in range(threshold_x, threshold_x + 60)
                for py in range(threshold_y - size, threshold_y + 2)]
        self.assertTrue(any(near(p, SECONDARY, 8) for p in band))
        self.assertFalse(any(min(p) > 200 for p in band))  # 白い字が無い（灰色は明るくても 147）
        _, _, number_size, unit_size, _ = ms.LANDSCAPE.number
        self.assertEqual(unit_size, 0)
        _, _, radius, width = ms.LANDSCAPE.ring
        self.assertLess(ms.rounded(number_size).getlength("100"), 2 * (radius - width) - 6)  # 「100」もリングの内側に収まる

    def test_large_layout_has_a_row_of_rings_and_the_counter_rows(self):
        # 2026-11-03、5.2 インチは、4 つのリングを横 1 列に、その下に件数の行（5xx・PHP エラー）を置く
        # （ユーザーが見本で選んだ。それまでの 2×2 は 2.25 倍の横置き）
        large = ms.LANDSCAPE_LARGE
        self.assertIs(ms.layout_for((1280, 720)), large)
        self.assertIs(ms.layout_for((480, 320)), ms.LANDSCAPE)
        self.assertIs(ms.layout_for((320, 480), portrait=True), ms.PORTRAIT)
        cfg = config(counters=COUNTERS)
        st = status_with_counters()
        big = ms.render(st, sm.assess(st, cfg, NOW), cfg, layout=large)
        self.assertEqual(big.size, (1280, 720))
        # リングは横 1 列で、隣と重ならず、横の区切り線の上に収まる。「100」もリングの内側に収まる
        _, cy, radius, width = large.ring
        xs = [x for x, _ in large.cells]
        self.assertEqual(len(xs), 4)
        self.assertTrue(all(b - a > 2 * radius + 20 for a, b in zip(xs, xs[1:])))
        # リングとしきい値の字は「直近 24 時間」の小見出しの上に収まる（上下のまとまりの間の罫線は 2026-11-03 に消した）
        self.assertEqual(large.dividers, ())
        caption_x, caption_y, _caption, caption_size, _w, _a = large.headings[-1]  # 「直近 24 時間」
        self.assertLess(cy + radius, large.threshold[1] - large.threshold[3])
        self.assertLess(large.threshold[1] + 3, caption_y - caption_size - 10)
        self.assertGreater(cy - radius, ms.BIG_BOX[2][1])  # 異常の 2 行の帯の下
        self.assertLess(ms.rounded(large.number[2]).getlength("100"), 2 * (radius - width) - 6)
        # 件数の行は画面の内側に収まる
        rows = large.counter_rows
        self.assertLessEqual(rows.top + rows.height * 2, 320)

    def test_counter_rows_show_the_total_and_red_bars_for_alarmed_hours(self):
        cfg = config(counters=COUNTERS)
        st = status_with_counters(hourly_5xx=(0,) * 21 + (1, 3, 12), alarmed_5xx=(False,) * 23 + (True,))
        image = ms.render(st, sm.assess(st, cfg, NOW), cfg, layout=ms.LANDSCAPE_LARGE)
        k, rows = ms.LANDSCAPE_LARGE.k, ms.LANDSCAPE_LARGE.counter_rows
        spark_x, spark_w, spark_h, bottom = rows.spark
        # 最後の時間（警報の条件を満たした）の棒は赤、その前の時間の棒は白
        y = round((rows.top + bottom - 2) * k)
        last = round((spark_x + spark_w * 23.5 / 24) * k)
        before = round((spark_x + spark_w * 22.5 / 24) * k)
        self.assertTrue(near(image.getpixel((last, y)), RED, 30))
        self.assertTrue(near(image.getpixel((before, y)), (255, 255, 255), 30))
        # 警報の条件を満たした時間があれば、件数（16）も赤。PHP の行（0 件）は白
        number_row = [image.getpixel((x, round((rows.top + rows.baseline - 8) * k))) for x in range(1050, 1180)]
        self.assertTrue(any(near(p, RED, 30) for p in number_row))

    def test_no_line_between_the_counter_rows(self):
        # 2026-11-04、5xx エラーと PHP エラーの行の間の罫線を消した（ユーザーの指示）。行の境目の高さは黒だけ
        cfg = config(counters=COUNTERS)
        st = status_with_counters()
        image = ms.render(st, sm.assess(st, cfg, NOW), cfg, layout=ms.LANDSCAPE_LARGE)
        k, rows = ms.LANDSCAPE_LARGE.k, ms.LANDSCAPE_LARGE.counter_rows
        y = round((rows.top + rows.height) * k)
        self.assertTrue(all(image.getpixel((x, y)) == BACKGROUND for x in range(round(rows.left * k), round(rows.right * k))))

    def test_counter_alert_turns_the_screen_red(self):
        # 2026-11-03、5xx・PHP エラーが警報の条件（5 分間の合計が alert_at 以上）を満たしたら画面全体を赤にする
        cfg = config(counters=COUNTERS, large_alerts=True)
        st = status_with_counters(latest_5xx=11)
        assessment = sm.assess(st, cfg, NOW)
        self.assertTrue(assessment.red)
        self.assertEqual(assessment.alerts[0], "5xx エラー 11 件（5 分間）")
        for layout in (ms.LANDSCAPE_LARGE, ms.LANDSCAPE):
            image = ms.render(st, assessment, cfg, layout=layout)
            self.assertEqual(image.getpixel((2, image.height - 2)), RED)

    def test_headings_under_a_two_line_alert_are_not_drawn(self):
        # 2 行の異常の文言の帯にかかる小見出しは描かない（「サーバー」の小見出しがあった 2026-11-03 に入れた仕組み。
        # 同日その小見出しは消したので、帯にかかる位置に小見出しを置いた配置で確かめる）
        cfg = config(counters=COUNTERS, large_alerts=True)
        long = "トップ 本文に必要な文字列が無い状態が続いていて、再読み込みしても戻らない"
        st = status_with_counters()
        assessment = sm.Assessment((long,), (), frozenset())
        layout = replace(ms.LANDSCAPE_LARGE, headings=((26.7, 54.2, "サーバー", 12, 6, "ls"),))
        image = ms.render(st, assessment, cfg, layout=layout)
        k = layout.k
        _hx, hy, _text, size, _w, _a = layout.headings[0]
        self.assertLessEqual(hy - size, ms.BIG_BOX[2][1])  # この小見出しは 2 行の帯にかかる位置にある
        bare = ms.render(st, assessment, cfg, layout=replace(layout, headings=()))
        band = (0, 0, 1280, round(ms.BIG_BOX[2][1] * k))  # 帯の下端までは、小見出しの無い配置と同じ
        self.assertEqual(image.crop(band).tobytes(), bare.crop(band).tobytes())

    def test_landscape_long_labels_fit_their_cells(self):
        # 2026-10-27 に名前を 18→22、2026-11-03 に 24 ピクセルにした。左の列の名前は右の列のリングの手前、
        # 右の列の名前はその下の「しきい値 90%」より右へ出ない
        label_x, _, _, label_size = ms.LANDSCAPE.label
        threshold_x, _, _, threshold_size = ms.LANDSCAPE.threshold
        width = max(font(label_size, 6).getlength(text) for text in ("ディスク", "スワップ"))
        self.assertLess(ms.LANDSCAPE.cells[2][0] + label_x + width, right_ring_left() - 12)
        self.assertLessEqual(label_x + width, threshold_x + font(threshold_size, SMALL_WEIGHT).getlength("しきい値 90%"))

    def test_job_incidents_show_an_orange_dot_on_black(self):
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),)
        image = self.render(status(incidents=incidents))
        self.assertEqual(image.getpixel((2, 300)), BACKGROUND)
        header = [image.getpixel((x, 20)) for x in range(116, 364)]
        self.assertTrue(any(near(p, ORANGE) for p in header))

    def test_missing_status_and_fetch_errors_still_render(self):
        self.assertEqual(self.render(None, "通信できません").size, (480, 320))
        self.assertEqual(self.render(status(values=(None, 61, 47, 3)), "通信できません").getpixel((2, 300)), RED)
        stale = status(age=timedelta(minutes=10))
        self.assertEqual(self.render(stale).getpixel((2, 300)), RED)

    def test_portrait(self):
        cfg = config()
        normal, alert = status(), status(values=(92, 61, 47, 3))
        image = ms.render(normal, sm.assess(normal, cfg, NOW), cfg, portrait=True)
        self.assertEqual((image.size, image.getpixel((2, 470))), ((320, 480), BACKGROUND))
        image = ms.render(alert, sm.assess(alert, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel((2, 470)), RED)
        # CPU（左上の区画）のリングの 3 時の位置は白、メモリ（右上）は薄い色
        cx, cy, radius, width = ms.PORTRAIT.ring
        self.assertTrue(near(image.getpixel((round(cx + radius - width / 2), 80 + cy)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel((round(160 + cx + radius - width / 2), 80 + cy)), (255, 255, 255)))

    def test_portrait_splits_two_or_more_alerts_into_two_lines(self):
        cfg = config()
        below_one_line = (40, ms.PORTRAIT.pill[3] + 8)  # 1 行の帯の下、2 行の帯の中
        one = status(values=(92, 61, 47, 3))
        self.assertEqual(len(sm.assess(one, cfg, NOW).alerts), 1)
        image = ms.render(one, sm.assess(one, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel(below_one_line), RED)
        two = status(values=(92, 90, 47, 3))
        self.assertEqual(len(sm.assess(two, cfg, NOW).alerts), 2)
        image = ms.render(two, sm.assess(two, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel(below_one_line), (255, 255, 255))


class LocalScreenTest(unittest.TestCase):
    """この Mac の状態の画面（local）が使う、下の行の量・色の決め打ち・見出しの文言（2026-10-15）。"""

    def render(self, **overrides):
        from claude_usage_display import local_monitor as lm
        from tests.test_local_monitor import NOW as LOCAL_NOW
        from tests.test_local_monitor import sample

        reading = lm.build(sample(**overrides), LOCAL_NOW)
        cfg = sm.MonitorConfig(title="Mac mini", region="-", keychain_service="-", metrics=lm.SPECS)
        return ms.render(reading.status, sm.Assessment((), reading.warnings, frozenset()), cfg, note=reading.note)

    def test_cpu_has_a_second_line_below_the_first(self):
        image = self.render()
        x, y = ms.LANDSCAPE.cells[0]
        threshold_x, threshold_y, _, size = ms.LANDSCAPE.threshold
        second = [image.getpixel((x + threshold_x + dx, y + threshold_y + ms.DETAIL_LINE - dy))
                  for dx in range(0, 60) for dy in range(1, size)]
        self.assertTrue(any(p != BACKGROUND for p in second))
        # メモリは 1 行だけ（2 行目の位置は空いている）
        x, y = ms.LANDSCAPE.cells[1]
        second = [image.getpixel((x + threshold_x + dx, y + threshold_y + ms.DETAIL_LINE - dy))
                  for dx in range(0, 60) for dy in range(1, size)]
        self.assertTrue(all(p == BACKGROUND for p in second))

    def test_memory_ring_follows_the_pressure_level(self):
        cx, cy, radius, width = ms.LANDSCAPE.ring
        x, y = ms.LANDSCAPE.cells[1]
        at_twelve = (round(x + cx), round(y + cy - radius + width / 2))  # 弧の始まり（12 時）
        self.assertTrue(near(self.render(memory=30, pressure=2).getpixel(at_twelve), ORANGE))
        self.assertTrue(near(self.render(memory=30, pressure=4).getpixel(at_twelve), RED))
        self.assertFalse(near(self.render(memory=95, pressure=1).getpixel(at_twelve), ORANGE))

    def test_note_is_shown_with_a_green_dot_and_warnings_replace_it(self):
        header = lambda image: [image.getpixel((px, round(ms.LANDSCAPE.dot_y))) for px in range(116, 364)]
        self.assertTrue(any(near(p, ms.GREEN) for p in header(self.render())))
        warned = header(self.render(pressure=2, swap_rate=1 << 20))
        self.assertTrue(any(near(p, ORANGE) for p in warned))
        self.assertFalse(any(near(p, ms.GREEN) for p in warned))
        # 段階 2 だけ（スワップの読み書きが無い）なら、見出しは緑のまま。リングの色は別に黄色になる
        quiet = header(self.render(pressure=2, swap_rate=0.0))
        self.assertTrue(any(near(p, ms.GREEN) for p in quiet))


class HeaderTest(unittest.TestCase):
    def test_logo_sits_left_of_the_title_on_black_and_red(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Image.new("RGBA", (40, 40), (0, 255, 0, 255)).save(f, format="PNG")
        self.addCleanup(Path(f.name).unlink)
        cfg = sm.MonitorConfig(**{**sm.load_config(str(Path(sm.__file__).parents[1] / "monitor.example.toml")).__dict__,
                                  "logo": f.name})
        for portrait in (False, True):
            layout = ms.PORTRAIT if portrait else ms.LANDSCAPE
            for st in (status(), status(values=(92, 61, 47, 3))):
                with self.subTest(portrait=portrait, red=st.metrics[0].value > 80):
                    image = ms.render(st, sm.assess(st, cfg, NOW), cfg, portrait=portrait)
                    center = (layout.inset + ICON_SIZE // 2, round(layout.title_baseline - ms.LOGO_RISE))
                    self.assertTrue(near(image.getpixel(center), (0, 255, 0)))
                    # 名前は、ロゴの枠と間の分だけ右から始まる
                    left = layout.inset + ICON_SIZE + ICON_GAP
                    row = range(layout.title_baseline - 12, layout.title_baseline)
                    background = image.getpixel((left - 2, layout.title_baseline - 6))
                    ink = [x for x in range(left - ICON_GAP + 1, left + 6)
                           if any(image.getpixel((x, y)) != background for y in row)]
                    self.assertTrue(ink and ink[0] >= left - 1, ink)

    def test_landscape_pill_moves_right_of_a_long_title(self):
        # 帯の左端（116）にかかる名前。直す前は、末尾が白い帯に隠れていた
        cfg = config(title="example.com")
        st = status(values=(92, 61, 47, 3))
        image = ms.render(st, sm.assess(st, cfg, NOW), cfg)
        end = ms.LANDSCAPE.inset + font(15, 6).getlength("example.com")
        self.assertGreater(end, ms.LANDSCAPE.pill[0])
        middle = (ms.LANDSCAPE.pill[1] + ms.LANDSCAPE.pill[3]) // 2
        gap = [image.getpixel((x, middle)) for x in range(round(end) + 2, round(end) + ms.TITLE_GAP - 1)]
        self.assertTrue(all(near(p, RED) for p in gap), gap)


class HiddenTitleTest(unittest.TestCase):
    """異常の文言を大きく出す設定（large_alerts = true）。異常のあるときだけ、見出しの名前を出さず、行いっぱいに出す。"""

    WIDTH = 296

    def test_short_text_stays_on_one_line_at_the_big_size(self):
        lines, f = ms._big_lines("監視の障害 1 件", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["監視の障害 1 件"])
        self.assertEqual(f.size, ms.BIG_SIZE)

    def test_name_and_reason_are_split_on_two_lines(self):
        lines, f = ms._big_lines("example job: 直近の実行が失敗", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["example job", "直近の実行が失敗"])
        self.assertLessEqual(f.size, ms.BIG_SMALL)

    def test_more_alerts_are_split_before_the_count_of_others(self):
        lines, f = ms._big_lines("トップ HTTP 503（期待 200）　ほか 1 件", self.WIDTH, 6)
        self.assertEqual(lines, ["トップ HTTP 503（期待 200）", "ほか 1 件"])
        self.assertTrue(all(f.getlength(line) <= self.WIDTH for line in lines))

    def test_job_count_is_split_before_the_bracket(self):
        lines, _ = ms._big_lines("ジョブ障害 2 件（nightly-backup ほか）", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["ジョブ障害 2 件", "nightly-backup ほか"])

    def test_text_without_separators_stays_on_one_line_when_it_fits(self):
        # 2026-11-02 の実機。区切りの無い文言が 17 ピクセルの 1 行に収まると、2 行目が空のまま 2 行分の帯になっていた
        text = 'ユーザー登録 本文に「id="edit-name"」が無い'
        lines, f = ms._big_lines(text, 416, 6)
        self.assertEqual(lines, [text])
        self.assertEqual(f.size, 18)  # 1 行に収まる最も大きい大きさ

    def test_big_text_has_equal_gaps_above_and_below(self):
        # 2026-11-02、実機で「テキスト下の padding が大きすぎる。上下の隙間を合わせて」（ユーザーの指示）
        cfg = config(title="example.com", large_alerts=True)
        for size in (ms.BIG_SIZE, 20, ms.BIG_MIN):
            for lines in (["監視の障害 1 件"], ["トップ HTTP 503（期待 200）", "ほか 1 件"]):
                with self.subTest(size=size, lines=len(lines)):
                    f = ms.font(size, 6)
                    top, bottom = ms.BIG_BOX[len(lines)]
                    baselines = ms._centered_baselines(lines, f, top, bottom)
                    ink_top = baselines[0] + f.getbbox(lines[0], anchor="ls")[1]
                    ink_bottom = baselines[-1] + f.getbbox(lines[-1], anchor="ls")[3]
                    self.assertAlmostEqual(ink_top - top, bottom - ink_bottom, places=6)
        # 赤の画面で、白い帯の中の赤い字の上下の隙間が、画素で 1 以内
        red = status(values=(92, 61, 47, 3))
        image = ms.render(red, sm.assess(red, cfg, NOW), cfg)
        column = range(60, 420)
        pill_rows = [y for y in range(0, 60) if near(image.getpixel((40, y)), (255, 255, 255), 30)]
        text_rows = [y for y in range(0, 60) if any(near(image.getpixel((x, y)), RED, 60) for x in column)
                     and min(pill_rows) < y < max(pill_rows)]
        gap_top, gap_bottom = min(text_rows) - min(pill_rows), max(pill_rows) - max(text_rows)
        self.assertLessEqual(abs(gap_top - gap_bottom), 1, (gap_top, gap_bottom))

    def test_text_that_cannot_be_split_is_cut_with_an_ellipsis(self):
        lines, f = ms._big_lines("あ" * 60, self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith("…"))
        self.assertTrue(all(f.getlength(line) <= self.WIDTH for line in lines))
        self.assertEqual(f.size, ms.BIG_MIN)

    def test_title_is_hidden_only_while_there_is_an_alert(self):
        normal, red = status(), status(values=(92, 61, 47, 3))
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),)
        warned = status(incidents=incidents)
        shown, large = config(title="example.com"), config(title="example.com", large_alerts=True)
        left = ms.LANDSCAPE.inset

        def title_ink(cfg, st):  # 名前があった位置（ロゴの無い設定なので左端）に、名前の白があるか
            # （2026-11-02 から、異常の文言も左端から出るので、オレンジの字とは色で見分ける）
            image = ms.render(st, sm.assess(st, cfg, NOW), cfg)
            return any(min(image.getpixel((x, 20))) > 200 for x in range(left, left + 60))

        # 異常が無いときは、設定があっても名前を出す
        self.assertTrue(title_ink(large, normal))
        # 異常のあるときだけ、名前を出さない（設定が無ければ出したまま）
        self.assertFalse(title_ink(large, warned))
        self.assertTrue(title_ink(shown, warned))
        # 赤の画面は、白い帯が名前の位置まで広がる（設定が無ければ、名前の右から始まる）
        wide = ms.render(red, sm.assess(red, large, NOW), large)
        narrow = ms.render(red, sm.assess(red, shown, NOW), shown)
        self.assertTrue(near(wide.getpixel((left + 30, 8)), (255, 255, 255)))
        self.assertFalse(near(narrow.getpixel((left + 30, 8)), (255, 255, 255)))

    def test_alert_hides_the_logo_and_the_time_and_uses_the_whole_row(self):
        # 2026-11-02、異常のときは、名前だけでなく左のロゴと右上の時刻も出さず、見出しの行をまるごと使う（ユーザーの指示）
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Image.new("RGBA", (40, 40), (0, 255, 0, 255)).save(f, format="PNG")
        self.addCleanup(Path(f.name).unlink)
        large = config(title="example.com", large_alerts=True, logo=f.name)
        inset, logo = ms.LANDSCAPE.inset, (ms.LANDSCAPE.inset + ICON_SIZE // 2, round(25 - ms.LOGO_RISE))
        # 赤の画面: 白い帯が左右の余白の内側いっぱいに広がり、ロゴも時刻も無い
        red = status(values=(92, 61, 47, 3))
        image = ms.render(red, sm.assess(red, large, NOW), large)
        self.assertTrue(near(image.getpixel((inset + 30, 8)), (255, 255, 255)))
        self.assertTrue(near(image.getpixel((480 - inset - 30, 8)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel(logo), (0, 255, 0)))
        # オレンジの注意: ロゴの緑も、時刻の白い字も無い
        warned = status(incidents=(sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),))
        image = ms.render(warned, sm.assess(warned, large, NOW), large)
        self.assertFalse(near(image.getpixel(logo), (0, 255, 0)))
        stamp = [image.getpixel((x, y)) for x in range(380, 460) for y in range(8, 30)]
        self.assertFalse(any(min(p) > 200 for p in stamp))
        # 異常が無いときは、ロゴと時刻を出す
        image = ms.render(status(), sm.assess(status(), large, NOW), large)
        self.assertTrue(near(image.getpixel(logo), (0, 255, 0)))
        stamp = [image.getpixel((x, y)) for x in range(380, 460) for y in range(8, 30)]
        self.assertTrue(any(min(p) > 200 for p in stamp))

    def test_warning_is_drawn_larger_on_two_lines(self):
        # 見出しの行をまるごと使う（2026-11-02）と 1 行に収まる文言が増えたので、2 行になる長い理由で確かめる
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗し、続けて行った再実行も同じ理由で失敗した",
                                 None),)
        st = status(incidents=incidents)
        large = config(title="example.com", large_alerts=True)
        image = ms.render(st, sm.assess(st, large, NOW), large)
        # 異常の文言（オレンジ）は、見出しの高さの外（35 ピクセルより下）にも、2 行目として出る
        rows = [y for y in range(0, 56) if any(near(image.getpixel((x, y)), ORANGE, 40) for x in range(120, 360))]
        self.assertGreater(max(rows) - min(rows), 30)

    def test_default_is_off(self):
        self.assertFalse(config().large_alerts)
        self.assertTrue(config(large_alerts=True).large_alerts)

    def test_portrait_ignores_the_setting(self):
        st = status(values=(92, 61, 47, 3))
        hidden = config(title="example.com", large_alerts=True)
        shown = config(title="example.com")
        a = ms.render(st, sm.assess(st, hidden, NOW), hidden, portrait=True)
        b = ms.render(st, sm.assess(st, shown, NOW), shown, portrait=True)
        self.assertEqual(a.tobytes(), b.tobytes())


if __name__ == "__main__":
    unittest.main()
