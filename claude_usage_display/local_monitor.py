"""この Mac の状態（CPU・メモリ・内蔵ディスク・外付けの SSD）の取得と、画面に出す値の組み立て。

``local`` コマンドが使う。画面はサーバーの状態の画面（``monitor_screen``）の横置きと同じ 2×2 で、リングの右の
下の行に、しきい値ではなく量を出す。設計の経緯と出典は ``docs/handover.md`` §4-15。

- どれも管理者権限なしで読み、WindowServer にも問い合わせない（``CGDisplayIsAsleep`` を問い合わせた直後に
  Mac が固まった件。§4-12）
- CPU: ``host_processor_info`` の CPU ごとの時間の差から、前回の取得からの平均を出す（1 分ごとに取れば 1 分の
  平均。一瞬の値だと短い山でも赤になるため）。高性能コアと高効率コアは、デバイスツリーの ``cluster-type``（P・E）で分ける
- メモリ: 使用率は ``100 - kern.memorystatus_level``。リングの色は割合ではなく ``kern.memorystatus_vm_pressure_level``
  （1 正常・2 警告・4 危険）で決める。macOS（圧縮が有効）の逼迫の判定は、圧縮されずに残るメモリの量で決まり、
  割合を使っていないため（xnu ``osfmk/vm/vm_pageout.c`` の ``VM_PRESSURE_NORMAL_TO_WARNING``）
- ディスク・SSD: ``kCFURLVolumeAvailableCapacityForImportantUsageKey``（purge で空く見込みの分を含む空き。
  CoreFoundation の ``CFURL.h``）。スナップショットなど自動で空く分まで「使用中」に数えない
- 見出しの行: 普段は最後のバックアップの時刻（緑）。異常があればその内容（オレンジ）。異常は、メモリの逼迫
  （スワップの量を添える）・熱による性能の制限・内蔵 SSD の SMART・バックアップが古いこと
- 最後のバックアップの時刻は、Time Machine の設定ファイル（``SnapshotDates``）から読む。launchd から起動すると
  フルディスクアクセスが無いため読めないので、そのときはバックアップ先のディスクのスナップショットの名前
  （``diskutil apfs listSnapshots`` の ``com.apple.TimeMachine.2026-10-16-062646.backup``。この Mac の時刻）から読む。
  バックアップ先は ``tmutil destinationinfo`` の Mount Point。どちらも launchd から読めることを 2026-10-16 に確かめた
  （``tmutil latestbackup`` はフルディスクアクセスが要る）。成功したバックアップだけがバックアップ先に残る
"""

from __future__ import annotations

import ctypes
import logging
import os
import plistlib
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .server_monitor import MetricSpec, MetricValue, ServerStatus

log = logging.getLogger("claude_usage_display")

JST = timezone(timedelta(hours=9))
# しきい値（2026-10-15 ユーザーが決めた）。メモリは色を逼迫の段階で決めるので、しきい値は使わない
SPECS = (MetricSpec("CPU", "local", "cpu", (), 80), MetricSpec("メモリ", "local", "memory", (), 85),
         MetricSpec("ディスク", "local", "disk", (), 90), MetricSpec("SSD", "local", "ssd", (), 90))
PRESSURE_TINT = {1: "normal", 2: "warning", 4: "critical"}  # kern.memorystatus_vm_pressure_level
# OSThermalNotification.h の macOS の段階（0 Nominal・1 Moderate・2 Heavy・3 Trapping・4 Sleeping）。Heavy から出す
THERMAL_WARNING = 2
BACKUP_STALE = timedelta(hours=36)  # 毎日のバックアップが 1 回抜けたら気付けるように
SMART_INTERVAL = 600  # 内蔵 SSD の SMART を読み直す間隔（秒）
TM_PLIST = "/Library/Preferences/com.apple.TimeMachine.plist"
GIB = 2 ** 30


@dataclass(frozen=True)
class Sample:
    """1 回の取得で読んだ値（画面に出す形にする前）。"""

    cpu: float | None
    performance: float | None  # 高性能コアの使用率の平均
    efficiency: float | None   # 高効率コアの使用率の平均
    memory: float              # 使用率
    memory_total: int          # バイト
    pressure: int              # kern.memorystatus_vm_pressure_level
    swap: int                  # 使用中のスワップ（バイト）
    disk: tuple[int, int] | None  # 全体・空き（バイト）
    ssd: tuple[int, int] | None
    thermal: int | None
    smart: str | None
    last_backup: datetime | None
    backup_running: bool = False
    backup_percent: float | None = None  # 0〜1


@dataclass(frozen=True)
class LocalReading:
    status: ServerStatus
    note: str | None              # 異常が無いときの見出しの行（緑）
    warnings: tuple[str, ...]     # 異常（オレンジ。画面には先頭を出す）
    pressure: int
    swap: int


def capacity_text(total: int, free: int) -> str:
    """「327/494 GB」「1.6/4.0 TB」。スラッシュの前後に空白を入れない（左の列の区切り線を越えないように）。"""
    used = total - free
    if total >= 10 ** 12:
        return f"{used / 10 ** 12:.1f}/{total / 10 ** 12:.1f} TB"
    return f"{used / 10 ** 9:.0f}/{total / 10 ** 9:.0f} GB"


def backup_line(last: datetime | None, running: bool, percent: float | None,
                now: datetime) -> tuple[str | None, str | None]:
    """（普段の文言, 異常の文言）。どちらか一方だけを返す。"""
    if running:
        return (f"バックアップ中 {percent * 100:.0f}%" if percent is not None else "バックアップ中"), None
    if last is None:
        return None, "バックアップの時刻を読めません"
    local = last.astimezone(JST)
    if now - last > BACKUP_STALE:
        days = (now.astimezone(JST).date() - local.date()).days
        return None, f"バックアップ {local.month}/{local.day}（{days} 日前）"
    clock = f"{local.hour}:{local.minute:02d}"
    if local.date() == now.astimezone(JST).date():
        return f"バックアップ {clock}", None
    return f"バックアップ {local.month}/{local.day} {clock}", None


def build(sample: Sample, now: datetime) -> LocalReading:
    """読んだ値を、画面の 4 つのリングと見出しの行にする。"""
    if sample.performance is not None and sample.efficiency is not None:
        cpu_detail = (f"性能 {sample.performance:.0f}%", f"効率 {sample.efficiency:.0f}%")
    else:
        cpu_detail = ()
    total_gib = sample.memory_total / GIB
    memory_detail = (f"{total_gib * sample.memory / 100:.1f}/{total_gib:.0f} GB",)

    def disk_metric(spec, pair, missing):
        if pair is None:
            return MetricValue(spec, None, now, None, (missing,))
        total, free = pair
        return MetricValue(spec, 100 * (total - free) / total, now, None, (capacity_text(total, free),))

    metrics = (MetricValue(SPECS[0], sample.cpu, now, None, cpu_detail),
               MetricValue(SPECS[1], sample.memory, now, None, memory_detail,
                           PRESSURE_TINT.get(sample.pressure, "critical" if sample.pressure > 4 else "normal")),
               disk_metric(SPECS[2], sample.disk, "読めません"),
               disk_metric(SPECS[3], sample.ssd, "未接続"))
    note, backup_warning = backup_line(sample.last_backup, sample.backup_running, sample.backup_percent, now)
    warnings = []
    if sample.pressure >= 2:
        word = "危険" if sample.pressure >= 4 else "逼迫"
        warnings.append(f"メモリ{word}　スワップ {sample.swap / GIB:.1f} GB")
    if sample.thermal is not None and sample.thermal >= THERMAL_WARNING:
        warnings.append("熱で性能を制限しています")
    if sample.smart not in (None, "Verified"):
        warnings.append(f"内蔵 SSD の SMART: {sample.smart}")
    if backup_warning:
        warnings.append(backup_warning)
    return LocalReading(ServerStatus(metrics, None, now), note, tuple(warnings), sample.pressure, sample.swap)


def demo_sample(case: str, now: datetime) -> Sample:
    """local --preview --demo の見本の値。normal は正常、warning はメモリの逼迫。"""
    backup = now.astimezone(JST).replace(hour=8, minute=33, second=0, microsecond=0)
    if backup > now:
        backup -= timedelta(days=1)
    warning = case == "warning"
    return Sample(cpu=33, performance=22, efficiency=40, memory=78 if warning else 44, memory_total=32 * GIB,
                  pressure=2 if warning else 1, swap=round(4.2 * GIB) if warning else 0,
                  disk=(494_384_795_648, 167_220_789_603), ssd=(4_000_109_887_488, 2_392_104_269_419), thermal=0,
                  smart="Verified", last_backup=backup)


# ---- 取得（ctypes とコマンド）

_libc = ctypes.CDLL("/usr/lib/libSystem.dylib")
_libc.mach_host_self.restype = ctypes.c_uint
_libc.host_processor_info.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                                      ctypes.POINTER(ctypes.POINTER(ctypes.c_int)), ctypes.POINTER(ctypes.c_uint)]
_libc.vm_deallocate.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
_libc.sysctlbyname.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p,
                               ctypes.c_size_t]
_libc.notify_register_check.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
_libc.notify_get_state.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]
PROCESSOR_CPU_LOAD_INFO = 2  # mach/processor_info.h。CPU ごとに user・system・idle・nice の 4 つ（CPU_STATE_MAX）


def cpu_ticks(host: int) -> list[tuple[int, int, int, int]]:
    count, info, size = ctypes.c_uint(), ctypes.POINTER(ctypes.c_int)(), ctypes.c_uint()
    result = _libc.host_processor_info(host, PROCESSOR_CPU_LOAD_INFO, ctypes.byref(count), ctypes.byref(info),
                                       ctypes.byref(size))
    if result != 0:
        raise OSError(f"host_processor_info が失敗しました（{result}）")
    try:
        return [tuple(info[i * 4 + j] & 0xFFFFFFFF for j in range(4)) for i in range(count.value)]
    finally:
        # 結果はカーネルが割り当てたページに入る。返さないと、1 分ごとに 1 ページずつ増え続ける
        task = ctypes.c_uint.in_dll(_libc, "mach_task_self_").value
        _libc.vm_deallocate(task, ctypes.cast(info, ctypes.c_void_p).value, size.value * ctypes.sizeof(ctypes.c_int))


def cpu_usage(before, after, kinds: list[str] | None) -> tuple[float | None, float | None, float | None]:
    """（全体, 高性能コア, 高効率コア）の使用率。``kinds`` は CPU の番号の順の P・E。"""
    rows = []
    for old, new in zip(before, after):
        user, system, idle, nice = ((n - o) % 2 ** 32 for o, n in zip(old, new))  # 32 ビットの数が一周しても差は正しい
        rows.append((user + system + nice, user + system + idle + nice))

    def share(selected):
        total = sum(t for _, t in selected)
        return 100 * sum(u for u, _ in selected) / total if total else None

    if not kinds or len(kinds) != len(rows):
        return share(rows), None, None
    return (share(rows), share([r for r, k in zip(rows, kinds) if k == "P"]),
            share([r for r, k in zip(rows, kinds) if k == "E"]))


def parse_cpu_kinds(text: str) -> list[str] | None:
    """``ioreg -p IODeviceTree -r -n cpus -l`` の ``cpuN`` ごとの ``cluster-type``（P・E）を番号の順に。"""
    kinds, current = {}, None
    for line in text.splitlines():
        match = re.search(r"\+-o cpu(\d+)@", line)
        if match:
            current = int(match.group(1))
            continue
        match = re.search(r'"cluster-type" = <"([A-Z])"', line)
        if match and current is not None:
            kinds[current], current = match.group(1), None
    if not kinds or sorted(kinds) != list(range(len(kinds))):
        return None
    return [kinds[i] for i in range(len(kinds))]


def _run(command: list[str], timeout: float = 10) -> str | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def sysctl(name: str, ctype=ctypes.c_int):
    value = ctype()
    size = ctypes.c_size_t(ctypes.sizeof(value))
    if _libc.sysctlbyname(name.encode(), ctypes.byref(value), ctypes.byref(size), None, 0) != 0:
        raise OSError(f"sysctl {name} を読めません")
    return value


class _SwapUsage(ctypes.Structure):  # sys/sysctl.h の struct xsw_usage
    _fields_ = [("total", ctypes.c_uint64), ("avail", ctypes.c_uint64), ("used", ctypes.c_uint64),
                ("pagesize", ctypes.c_uint32), ("encrypted", ctypes.c_bool)]


def volume(path: str) -> tuple[int, int] | None:
    """（全体, purge で空く見込みの分を含む空き）。つながっていなければ None。"""
    if path != "/" and not os.path.ismount(path):  # 外したあとに残った空のフォルダを、内蔵の値で読まないように
        return None
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                           ctypes.c_bool]
    cf.CFURLCopyResourcePropertyForKey.restype = ctypes.c_bool
    cf.CFURLCopyResourcePropertyForKey.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                                   ctypes.c_void_p]
    cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    raw = path.encode()
    url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), True)
    if not url:
        return None
    try:
        values = []
        for key in ("kCFURLVolumeTotalCapacityKey", "kCFURLVolumeAvailableCapacityForImportantUsageKey"):
            number = ctypes.c_void_p()
            if not cf.CFURLCopyResourcePropertyForKey(url, ctypes.c_void_p.in_dll(cf, key), ctypes.byref(number),
                                                      None) or not number:
                return None
            out = ctypes.c_int64()
            cf.CFNumberGetValue(number, 4, ctypes.byref(out))  # kCFNumberSInt64Type
            cf.CFRelease(number)
            values.append(out.value)
        total, free = values
        return (total, free) if total > 0 else None
    finally:
        cf.CFRelease(url)


def parse_destination_mounts(text: str) -> list[str]:
    """``tmutil destinationinfo`` の「Mount Point   : /Volumes/backup」（つながっているバックアップ先だけに出る）。"""
    return [m.group(1).strip() for m in re.finditer(r"^Mount Point\s*:\s*(.+)$", text, re.MULTILINE)]


def parse_backup_snapshots(text: str) -> datetime | None:
    """``diskutil apfs listSnapshots`` の ``com.apple.TimeMachine.2026-10-16-062646.backup``（この Mac の時刻）の最新。"""
    stamps = re.findall(r"com\.apple\.TimeMachine\.(\d{4}-\d{2}-\d{2}-\d{6})\.backup", text)
    if not stamps:
        return None
    return datetime.strptime(max(stamps), "%Y-%m-%d-%H%M%S").astimezone(timezone.utc)


def last_backup() -> datetime | None:
    try:
        with open(TM_PLIST, "rb") as f:
            data = plistlib.load(f)
        dates = [d for destination in data.get("Destinations", []) for d in destination.get("SnapshotDates", [])]
        if dates:
            return max(dates).replace(tzinfo=timezone.utc)  # plistlib の日時は UTC（タイムゾーン無し）
    except (OSError, plistlib.InvalidFileException):
        pass  # launchd から起動すると、フルディスクアクセスが無いので読めない
    found = []
    for mount in parse_destination_mounts(_run(["/usr/bin/tmutil", "destinationinfo"]) or ""):
        stamp = parse_backup_snapshots(_run(["/usr/sbin/diskutil", "apfs", "listSnapshots", mount], timeout=30) or "")
        if stamp:
            found.append(stamp)
    return max(found) if found else None


def backup_progress() -> tuple[bool, float | None]:
    text = _run(["tmutil", "status", "-X"])
    if not text:
        return False, None
    try:
        data = plistlib.loads(text.encode())
    except plistlib.InvalidFileException:
        return False, None
    if not data.get("Running"):
        return False, None
    percent = data.get("Progress", {}).get("Percent", data.get("Percent"))
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        return True, None
    return True, percent if 0 <= percent <= 1 else None


def machine_name() -> str:
    """見出しの名前の既定（「Mac mini」などの機種名）。"""
    text = _run(["system_profiler", "SPHardwareDataType", "-xml"], timeout=30)
    try:
        return plistlib.loads(text.encode())[0]["_items"][0]["machine_name"]
    except (AttributeError, IndexError, KeyError, TypeError, plistlib.InvalidFileException):
        return "Mac"


class LocalReader:
    def __init__(self, ssd_path: str = "/Volumes/SSD"):
        self.ssd_path = ssd_path
        self.host = _libc.mach_host_self()
        self.kinds = parse_cpu_kinds(_run(["ioreg", "-p", "IODeviceTree", "-r", "-n", "cpus", "-l", "-w0"]) or "")
        if self.kinds is None:
            log.warning("CPU の種類（高性能・高効率）を読めません。CPU は全体の使用率だけを出します")
        self.previous: list | None = None
        self.memory_total = sysctl("hw.memsize", ctypes.c_uint64).value
        name = ctypes.c_char_p.in_dll(_libc, "kOSThermalNotificationPressureLevelName").value
        token = ctypes.c_int()
        self.thermal_token = token.value if _libc.notify_register_check(name, ctypes.byref(token)) == 0 else None
        self.smart_disk = self._internal_disk()
        self.smart: str | None = None
        self.smart_read_at = float("-inf")

    @staticmethod
    def _internal_disk() -> str | None:
        """起動ディスクの物理ディスク（disk0 など）。APFS の物理ストア（disk0s2）から。"""
        text = _run(["diskutil", "info", "-plist", "/"])
        try:
            store = plistlib.loads(text.encode())["APFSPhysicalStores"][0]["APFSPhysicalStore"]
        except (AttributeError, IndexError, KeyError, TypeError, plistlib.InvalidFileException):
            return None
        match = re.match(r"disk\d+", store)
        return match.group(0) if match else None

    def _smart(self) -> str | None:
        if self.smart_disk and time.monotonic() - self.smart_read_at >= SMART_INTERVAL:
            text = _run(["diskutil", "info", "-plist", self.smart_disk])
            try:
                self.smart = plistlib.loads(text.encode()).get("SMARTStatus")
            except (AttributeError, plistlib.InvalidFileException):
                self.smart = None
            self.smart_read_at = time.monotonic()
        return self.smart

    def _thermal(self) -> int | None:
        state = ctypes.c_uint64()
        if self.thermal_token is None or _libc.notify_get_state(self.thermal_token, ctypes.byref(state)) != 0:
            return None
        return state.value

    def sample(self) -> Sample:
        ticks = cpu_ticks(self.host)
        if self.previous is None:  # 初回だけ 1 秒の差を取る。以降は前回の取得からの平均
            time.sleep(1)
            self.previous, ticks = ticks, cpu_ticks(self.host)
        cpu, performance, efficiency = cpu_usage(self.previous, ticks, self.kinds)
        self.previous = ticks
        swap = _SwapUsage()
        size = ctypes.c_size_t(ctypes.sizeof(swap))
        if _libc.sysctlbyname(b"vm.swapusage", ctypes.byref(swap), ctypes.byref(size), None, 0) != 0:
            raise OSError("sysctl vm.swapusage を読めません")
        running, percent = backup_progress()
        return Sample(cpu=cpu, performance=performance, efficiency=efficiency,
                      memory=100 - sysctl("kern.memorystatus_level").value, memory_total=self.memory_total,
                      pressure=sysctl("kern.memorystatus_vm_pressure_level").value, swap=swap.used,
                      disk=volume("/"), ssd=volume(self.ssd_path), thermal=self._thermal(), smart=self._smart(),
                      last_backup=last_backup(), backup_running=running, backup_percent=percent)

    def fetch(self, now: datetime | None = None) -> LocalReading:
        sample = self.sample()
        return build(sample, now or datetime.now(timezone.utc))
