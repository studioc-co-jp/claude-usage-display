import argparse
import errno
import io
import unittest
from datetime import datetime, timezone
from unittest import mock

from PIL import Image

from claude_usage_display import __main__ as cli
from claude_usage_display.turing import Command, encode_command
from claude_usage_display.turzx_usb import CMD_PNG, CMD_SYNC
from claude_usage_display.usage import Meter, Snapshot, UsageError
from tests.test_turzx_usb import FakeTransport as FakeTurzxTransport
from tests.test_turzx_usb import decrypt

LANDSCAPE_HEADER = encode_command(Command.DISPLAY_BITMAP, 0, 0, 479, 319)


def make_args(**overrides):
    values = dict(model="Fable", brightness=30, flip=False, interval=120, save_png=None, theme="gauge")
    values.update(overrides)
    return argparse.Namespace(**values)


def snapshot():
    now = datetime.now(timezone.utc)
    return Snapshot((Meter("5時間", 26, now), Meter("週次", 3, now), Meter("Fable週次", 0, now)), now)


class StopAfterFrames:
    """横向きの画面を ``frames`` 枚受け取ったら、ループに終了の合図を出す送信路。"""

    def __init__(self, runner, frames=1):
        self.runner = runner
        self.frames = frames
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))
        if data == LANDSCAPE_HEADER:
            self.frames -= 1
        elif self.frames == 0 and sum(map(len, self.writes[self.writes.index(LANDSCAPE_HEADER) + 1:])) == 480 * 320 * 2:
            self.runner.stop.set()

    def close(self):
        pass


class FailOnFrame:
    """画面の送信を始めたところで ``error`` を出し、ループに終了の合図を出す送信路。"""

    def __init__(self, runner, error):
        self.runner = runner
        self.error = error

    def write(self, data):
        if data == LANDSCAPE_HEADER:
            self.runner.stop.set()
            raise self.error

    def close(self):
        pass


class RunnerTest(unittest.TestCase):
    def setUp(self):
        # 5.2 インチは先に探されるので、ここでは未接続にして 3.5 インチ（rev A）の経路を試す
        patcher = mock.patch.object(cli.TurzxUsbTransport, "open", side_effect=cli.DeviceNotFound("未接続"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_connects_fetches_and_sends_one_full_frame(self):
        runner = cli.Runner(make_args())
        transport = StopAfterFrames(runner)
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", return_value=snapshot()) as fetch:
            self.assertEqual(runner.loop(), 0)
        fetch.assert_called_once_with("Fable")
        self.assertIn(LANDSCAPE_HEADER, transport.writes)
        self.assertIsNone(runner.status)

    def test_fetch_error_keeps_running_and_respects_retry_after(self):
        runner = cli.Runner(make_args())
        transport = StopAfterFrames(runner)
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", side_effect=UsageError("取得の間隔を空けています", 900)), \
                mock.patch.object(cli.time, "monotonic", return_value=1000.0):
            runner.loop()
        self.assertEqual(runner.status, "取得の間隔を空けています")
        self.assertEqual(runner.next_fetch, 1900.0)

    def test_rate_limit_is_logged_every_time_with_wait_and_recovery_duration(self):
        runner = cli.Runner(make_args())
        limited = UsageError("取得の間隔を空けています", 212, rate_limited=True, detail="HTTP 429。Retry-After: 212 → 212 秒")
        jst = cli.render.JST
        clock = iter([datetime(2026, 10, 9, 22, 56, 29, tzinfo=jst), datetime(2026, 10, 9, 22, 56, 29, tzinfo=jst),
                      datetime(2026, 10, 9, 23, 0, 1, tzinfo=jst), datetime(2026, 10, 9, 23, 3, 35, tzinfo=jst)])
        fake_datetime = mock.Mock(wraps=datetime, now=lambda tz=None: next(clock))
        with mock.patch.object(cli, "fetch_snapshot", side_effect=[limited, limited, snapshot()]), \
                mock.patch.object(cli, "datetime", fake_datetime), \
                mock.patch.object(cli.time, "monotonic", side_effect=[0.0, 1000.0, 2000.0]), \
                self.assertLogs(cli.log, "INFO") as logs:
            for _ in range(3):
                runner._fetch_if_due()
        self.assertEqual([r.getMessage() for r in logs.records], [
            "取得の間隔を空けるよう求められました（HTTP 429。Retry-After: 212 → 212 秒。次の取得は 23:00:01）",
            "取得の間隔を空けるよう求められました（HTTP 429。Retry-After: 212 → 212 秒。次の取得は 23:03:33）",
            "取得が戻りました（22:56:29 から 7 分 6 秒）",
        ])
        self.assertIsNone(runner.status)

    def test_other_failures_are_logged_once_while_they_continue(self):
        runner = cli.Runner(make_args())
        with mock.patch.object(cli, "fetch_snapshot", side_effect=UsageError("通信できません")), \
                mock.patch.object(cli.time, "monotonic", side_effect=[0.0, 1000.0]), \
                self.assertLogs(cli.log, "WARNING") as logs:
            runner._fetch_if_due()
            runner._fetch_if_due()
        self.assertEqual(len(logs.records), 1)

    def test_waits_without_fetching_while_device_is_absent(self):
        runner = cli.Runner(make_args())

        def absent():
            runner.stop.set()
            raise cli.DeviceNotFound("未接続")

        with mock.patch.object(cli.UsbTransport, "open", side_effect=absent), \
                mock.patch.object(cli, "fetch_snapshot") as fetch:
            runner.loop()
        fetch.assert_not_called()

    def test_labels_follow_model_when_nothing_was_fetched(self):
        runner = cli.Runner(make_args(model="Opus"))
        transport = StopAfterFrames(runner)
        draw = mock.Mock(wraps=cli.THEMES["gauge"])
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", side_effect=UsageError("通信できません")), \
                mock.patch.dict(cli.THEMES, {"gauge": draw}), self.assertLogs(cli.log, "WARNING"):
            runner.loop()
        self.assertEqual(draw.call_args.args[3], ("5時間", "週次", "Opus週次"))

    def test_unplugging_is_logged_in_one_line_and_waits_again(self):
        import usb.core

        for error, level, traceback in ((usb.core.USBError("No such device", -4, errno.ENODEV), "WARNING", False),
                                        (usb.core.USBError("Pipe error", -9, errno.EPIPE), "ERROR", True)):
            runner = cli.Runner(make_args())
            with self.subTest(errno=error.errno), \
                    mock.patch.object(cli.UsbTransport, "open", return_value=FailOnFrame(runner, error)), \
                    mock.patch.object(cli, "fetch_snapshot", return_value=snapshot()), \
                    self.assertLogs(cli.log, "WARNING") as logs:
                runner.loop()
                self.assertIsNone(runner.display)
                record = logs.records[0]
                self.assertEqual((record.levelname, record.exc_info is not None), (level, traceback))


class StopAfterImage(FakeTurzxTransport):
    """5.2 インチの偽の送信路。画像を 1 枚受け取ったら、ループに終了の合図を出す。"""

    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def write(self, data):
        super().write(data)
        if decrypt(data)[0] == CMD_PNG:
            self.runner.stop.set()


class TurzxRunnerTest(unittest.TestCase):
    def test_prefers_turzx_and_sends_letterboxed_portrait_png(self):
        runner = cli.Runner(make_args())
        transport = StopAfterImage(runner)
        with mock.patch.object(cli.TurzxUsbTransport, "open", return_value=(transport, 0x0050)), \
                mock.patch.object(cli.UsbTransport, "open") as rev_a, \
                mock.patch.object(cli, "fetch_snapshot", return_value=snapshot()):
            self.assertEqual(runner.loop(), 0)
        rev_a.assert_not_called()
        self.assertTrue(transport.drained)
        self.assertEqual(transport.commands()[0], CMD_SYNC)
        sent = Image.open(io.BytesIO(transport.writes[-1][512:])).convert("RGB")
        self.assertEqual(sent.size, (720, 1280))
        # ゲージ型は 1280×720 で直接描く。横向きの (60, 400) は左のカードの面で、
        # 時計回りに 90 度回した縦長では (719 - 400, 60) に来る
        self.assertEqual(sent.getpixel((319, 60)), cli.gauge.CARD)

    def test_classic_theme_is_letterboxed_on_the_larger_screen(self):
        runner = cli.Runner(make_args(theme="classic"))
        transport = StopAfterImage(runner)
        with mock.patch.object(cli.TurzxUsbTransport, "open", return_value=(transport, 0x0050)), \
                mock.patch.object(cli, "fetch_snapshot", return_value=snapshot()):
            runner.loop()
        sent = Image.open(io.BytesIO(transport.writes[-1][512:])).convert("RGB")
        # 480×320 を 2.25 倍の 1080×720 にして中央に置くので、横向きの左右 100 ピクセルは黒い。
        # 縦長に回した後は、上下の 100 ピクセルに当たる
        self.assertEqual(sent.getpixel((360, 50)), (0, 0, 0))
        self.assertEqual(sent.getpixel((360, 1229)), (0, 0, 0))
        self.assertNotEqual(sent.getpixel((360, 640)), (0, 0, 0))


class FitToTest(unittest.TestCase):
    def test_same_size_is_returned_as_is(self):
        image = Image.new("RGB", (480, 320))
        self.assertIs(cli.fit_to(image, (480, 320)), image)

    def test_keeps_aspect_ratio_and_centers(self):
        fitted = cli.fit_to(Image.new("RGB", (480, 320), (255, 255, 255)), (1280, 720))
        self.assertEqual(fitted.size, (1280, 720))
        self.assertEqual(fitted.getbbox(), (100, 0, 1180, 720))


class ArgumentsTest(unittest.TestCase):
    def setUp(self):
        # main() はログの出力先を設定する。後に続くテストの出力にログが混ざらないよう止める
        patcher = mock.patch.object(cli.logging, "basicConfig")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_out_of_range_options_before_starting(self):
        for argv in (["run", "--brightness", "101"], ["run", "--brightness", "-1"],
                     ["test-pattern", "--brightness", "101"], ["run", "--interval", "59"],
                     ["run", "--theme", "unknown"]):
            with self.subTest(argv=argv), mock.patch.object(cli, "cmd_run") as run, \
                    mock.patch.object(cli, "cmd_test_pattern") as test_pattern, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(argv)
                self.assertEqual(raised.exception.code, 2)
                run.assert_not_called()
                test_pattern.assert_not_called()

    def test_accepts_brightness_bounds(self):
        for value in ("0", "100"):
            with self.subTest(value=value), mock.patch.object(cli, "cmd_run", return_value=0) as run:
                self.assertEqual(cli.main(["run", "--brightness", value]), 0)
                self.assertEqual(run.call_args.args[0].brightness, int(value))

    def test_preview_size(self):
        for argv, expected in ((["preview"], "480x320"), (["preview", "--size", "1280x720"], "1280x720")):
            with self.subTest(argv=argv), mock.patch.object(cli, "cmd_preview", return_value=0) as preview:
                cli.main(argv)
                self.assertEqual(preview.call_args.args[0].size, expected)

    def test_theme_defaults_to_gauge_and_classic_stays_available(self):
        for argv, expected in ((["run"], "gauge"), (["run", "--theme", "classic"], "classic"),
                               (["preview", "--theme", "classic"], "classic")):
            with self.subTest(argv=argv), mock.patch.object(cli, "cmd_run", return_value=0) as run, \
                    mock.patch.object(cli, "cmd_preview", return_value=0) as preview:
                cli.main(argv)
                called = run if argv[0] == "run" else preview
                self.assertEqual(called.call_args.args[0].theme, expected)


if __name__ == "__main__":
    unittest.main()
