# taskbar_corner_meter.py  (dynamic units version)
import sys
import time
import psutil
from dataclasses import dataclass
from typing import Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout

import win32gui
import win32con

APP_NAME = "Taskbar Corner Net Meter"
REFRESH_MS = 500   # set to 500 for ~0.5s updates
MARGIN_PX = 2
W, H = 220, 24

# ===== Unit settings =====
# Start in 'bits' (bps, Kbps, Mbps...). Press Ctrl+Shift+U to toggle to 'bytes' (B/s, KB/s, MB/s...)
UNITS_MODE = "bits"     # "bits" or "bytes"
FORCE_UNIT = None       # e.g., "Mbps" or "KB/s" to force a unit; otherwise auto-scale. Leave as None for auto.

@dataclass
class Snapshot:
    sent: int
    recv: int
    ts: float

def get_tray_rect() -> Optional[Tuple[int, int, int, int]]:
    tray = win32gui.FindWindow("Shell_TrayWnd", None)
    if not tray:
        return None
    child = None
    def enum_child(h, _):
        nonlocal child
        if win32gui.GetClassName(h) == "TrayNotifyWnd":
            child = h
            return False
        return True
    try:
        win32gui.EnumChildWindows(tray, enum_child, None)
    except win32gui.error:
        pass
    target = child if child else tray
    try:
        return win32gui.GetWindowRect(target)
    except win32gui.error:
        return None

def format_rate(bytes_per_sec: float, mode: str = "bits", force_unit: Optional[str] = None) -> str:
    """
    Format throughput with auto-scaling.
    mode='bits'  -> bps, Kbps, Mbps, Gbps, Tbps (1000 steps)
    mode='bytes' -> B/s, KB/s, MB/s, GB/s, TB/s (1024 steps)
    """
    if mode == "bytes":
        value = bytes_per_sec
        units = ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]
        step = 1024.0
    else:
        value = bytes_per_sec * 8.0  # bits per second
        units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"]
        step = 1000.0

    if force_unit and force_unit in units:
        idx = units.index(force_unit)
        scaled = value / (step ** idx)
        return _fmt_value(scaled) + f" {force_unit}"

    # auto-scale
    idx = 0
    while value >= step and idx < len(units) - 1:
        value /= step
        idx += 1
    return _fmt_value(value) + f" {units[idx]}"

def _fmt_value(v: float) -> str:
    # nice rounding: more precision for smaller numbers
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    if v >= 1:
        return f"{v:.2f}"
    # For sub-1, show two decimals if meaningful, else zero
    return f"{v:.2f}" if v > 0 else "0"

def color_for_mbps(mbps: float) -> str:
    if mbps < 5:   return "#46BE5A"   # green
    if mbps < 50:  return "#FFAA28"   # amber
    return "#E64646"                  # red

class CornerStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.label = QLabel("Initializing…")
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        self.label.setFont(f)
        self.label.setStyleSheet("color: white;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.addWidget(self.label)

        self.resize(W, H)
        self.click_through = True
        self.apply_click_through(True)
        self._drag = None

        # Shortcuts
        self.short_lock = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self.short_lock.activated.connect(self.toggle_lock)
        self.short_quit = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        self.short_quit.activated.connect(QApplication.instance().quit)
        self.short_units = QShortcut(QKeySequence("Ctrl+Shift+U"), self)
        self.short_units.activated.connect(self.toggle_units)

        self.snap_to_tray()
        self.update_tooltip()

    def toggle_units(self):
        global UNITS_MODE
        UNITS_MODE = "bytes" if UNITS_MODE == "bits" else "bits"
        self.update_tooltip()

    def update_tooltip(self):
        state = "LOCKED (click-through)" if self.click_through else "UNLOCKED (draggable)"
        self.setToolTip(f"{APP_NAME}\n{state}\nUnits: {UNITS_MODE}\n"
                        f"Ctrl+Shift+L lock | Ctrl+Shift+U units | Ctrl+Shift+Q quit")

    def apply_click_through(self, enable: bool):
        hwnd = int(self.winId())
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enable:
            ex |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
        else:
            ex &= ~(win32con.WS_EX_TRANSPARENT)
            ex |= win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)

    def toggle_lock(self):
        self.click_through = not self.click_through
        self.apply_click_through(self.click_through)
        if self.click_through:
            self.snap_to_tray()
        self.update_tooltip()

    def mousePressEvent(self, e):
        if self.click_through: return
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.click_through or self._drag is None: return
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self.click_through: return
        self._drag = None

    def paintEvent(self, _):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(255,255,255,40))
        p.setBrush(QColor(18,18,20,220))
        p.drawRoundedRect(self.rect(), 8, 8)

    def snap_to_tray(self):
        rect = get_tray_rect()
        if not rect:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.right() - self.width() - MARGIN_PX,
                      screen.bottom() - self.height() - MARGIN_PX)
            return

        l, t, r, b = rect
        screen = QApplication.primaryScreen().geometry()
        x = r - self.width() - MARGIN_PX
        y = t - self.height() - MARGIN_PX
        if abs(t - screen.top()) < 10:          # top taskbar
            y = b + MARGIN_PX
        if abs(l - screen.left()) < 10:         # left taskbar
            x = r + MARGIN_PX; y = b - self.height() - MARGIN_PX
        if abs(r - screen.right()) < 10:        # right taskbar
            x = l - self.width() - MARGIN_PX; y = b - self.height() - MARGIN_PX
        self.move(x, y)

class App(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.strip = CornerStrip()
        self.strip.show()

        self.prev: Optional[Snapshot] = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)

        self.snap_timer = QTimer(self)
        self.snap_timer.timeout.connect(self.strip.snap_to_tray)
        self.snap_timer.start(5000)

    def refresh(self):
        global UNITS_MODE, FORCE_UNIT
        # Aggregate all NICs
        c = psutil.net_io_counters(pernic=False)
        now = time.time()
        if self.prev is None:
            self.prev = Snapshot(c.bytes_sent, c.bytes_recv, now)
            return

        dt = max(1e-6, now - self.prev.ts)
        up_Bps = (c.bytes_sent - self.prev.sent) / dt
        dn_Bps = (c.bytes_recv - self.prev.recv) / dt

        # Colors use Mbps equivalent for consistent thresholds
        up_Mbps = (up_Bps * 8.0) / 1_000_000
        dn_Mbps = (dn_Bps * 8.0) / 1_000_000

        up_txt = format_rate(up_Bps, mode=UNITS_MODE, force_unit=FORCE_UNIT)
        dn_txt = format_rate(dn_Bps, mode=UNITS_MODE, force_unit=FORCE_UNIT)

        text = (
            f"<span style='color:{color_for_mbps(dn_Mbps)};'>⬇ {dn_txt}</span>"
            f" <span style='color:#8a8a8a;'>|</span> "
            f"<span style='color:{color_for_mbps(up_Mbps)};'>⬆ {up_txt}</span>"
        )
        self.strip.label.setText(text)
        self.prev = Snapshot(c.bytes_sent, c.bytes_recv, now)

def main():
    app = App(sys.argv)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
