import sys
import time
import psutil
from dataclasses import dataclass
from typing import Optional, Tuple

# PyQt6 UI
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout

# pywin32 to locate the tray area reliably
import win32gui
import win32con
import win32api

APP_NAME = "Taskbar Corner Net Meter"
REFRESH_MS = 1000   # set to 500 for ~0.5s updates
MARGIN_PX = 2       # vertical gap from the taskbar/tray
W, H = 220, 24      # strip size

@dataclass
class Snapshot:
    sent: int
    recv: int
    ts: float

def get_tray_rect() -> Optional[Tuple[int, int, int, int]]:
    """
    Returns (left, top, right, bottom) of the tray (notification area) window.
    Falls back to the taskbar if the tray child is not found.
    """
    tray = win32gui.FindWindow("Shell_TrayWnd", None)
    if not tray:
        return None
    # Try to get the 'TrayNotifyWnd' child (the actual notification area)
    child = None
    def enum_child(h, l):
        nonlocal child
        cls = win32gui.GetClassName(h)
        if cls == "TrayNotifyWnd":
            child = h
            return False
        return True
    try:
        win32gui.EnumChildWindows(tray, enum_child, None)
    except win32gui.error:
        pass
    target = child if child else tray
    try:
        return win32gui.GetWindowRect(target)  # (l,t,r,b)
    except win32gui.error:
        return None

def human_mbps(bps: float) -> str:
    mbps = (bps * 8) / 1_000_000
    if mbps >= 0.10:
        return f"{mbps:.2f} Mbps"
    kbps = (bps * 8) / 1_000
    return f"{kbps:.0f} Kbps"

class CornerStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setObjectName("corner_strip")
        # Frameless, always-on-top, tool window (no taskbar button)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # Pretty + transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Content
        self.label = QLabel("Initializing…")
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        self.label.setFont(f)
        self.label.setStyleSheet("color: white;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.addWidget(self.label)

        self.resize(W, H)

        # Click-through by default
        self.click_through = True
        self.apply_click_through(True)

        # Movement (when unlocked)
        self._drag = None

        # Keyboard shortcuts
        self.short_lock = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self.short_lock.activated.connect(self.toggle_lock)
        self.short_quit = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        self.short_quit.activated.connect(QApplication.instance().quit)

        self.snap_to_tray()

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
        # Visual hint
        state = "LOCKED (click-through)" if self.click_through else "UNLOCKED (draggable)"
        self.setToolTip(f"{APP_NAME}\n{state}\nCtrl+Shift+L to toggle, Ctrl+Shift+Q to quit")

    def mousePressEvent(self, e):
        if self.click_through:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.click_through or self._drag is None:
            return
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self.click_through:
            return
        self._drag = None

    def paintEvent(self, e):
        # Rounded translucent background
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(255,255,255,40))
        p.setBrush(QColor(18,18,20,220))
        p.drawRoundedRect(self.rect(), 8, 8)

    def snap_to_tray(self):
        rect = get_tray_rect()
        if not rect:
            # Fallback: bottom-right of primary screen
            screen = QApplication.primaryScreen().geometry()
            x = screen.right() - self.width() - MARGIN_PX
            y = screen.bottom() - self.height() - MARGIN_PX
            self.move(x, y)
            return

        l, t, r, b = rect
        # Determine taskbar edge by comparing tray rect to screen rect
        screen = QApplication.primaryScreen().geometry()
        # Default: bottom taskbar
        x = r - self.width() - MARGIN_PX
        y = t - self.height() - MARGIN_PX

        # If taskbar is on top
        if abs(t - screen.top()) < 10:
            y = b + MARGIN_PX
        # If taskbar is on left
        if abs(l - screen.left()) < 10:
            x = r + MARGIN_PX
            y = b - self.height() - MARGIN_PX
        # If taskbar is on right
        if abs(r - screen.right()) < 10:
            x = l - self.width() - MARGIN_PX
            y = b - self.height() - MARGIN_PX

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
        self.timer.start(REFRESH_MS)   # set to 500 for 0.5s

        # Re-snap occasionally (multi-monitor/taskbar move)
        self.snap_timer = QTimer(self)
        self.snap_timer.timeout.connect(self.strip.snap_to_tray)
        self.snap_timer.start(5000)

    def refresh(self):
        # Aggregate all adapters for robust reading
        c_tot = psutil.net_io_counters(pernic=False)
        now = time.time()
        if self.prev is None:
            self.prev = Snapshot(c_tot.bytes_sent, c_tot.bytes_recv, now)
            return

        dt = max(1e-6, now - self.prev.ts)
        up_bps = (c_tot.bytes_sent - self.prev.sent) / dt
        dn_bps = (c_tot.bytes_recv - self.prev.recv) / dt

        up_mbps = (up_bps * 8) / 1_000_000
        dn_mbps = (dn_bps * 8) / 1_000_000

        # Color ramp
        def color(mbps: float):
            if mbps < 5: return "#46BE5A"
            if mbps < 50: return "#FFAA28"
            return "#E64646"

        text = (
            f"<span style='color:{color(dn_mbps)};'>⬇ {dn_mbps:.2f} Mbps</span>"
            f" <span style='color:#8a8a8a;'>|</span> "
            f"<span style='color:{color(up_mbps)};'>⬆ {up_mbps:.2f} Mbps</span>"
        )
        self.strip.label.setText(text)

        self.prev = Snapshot(c_tot.bytes_sent, c_tot.bytes_recv, now)

def main():
    app = App(sys.argv)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
