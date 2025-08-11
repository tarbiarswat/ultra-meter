# ultra_meter.py
import os, sys, json, time, winreg
from dataclasses import dataclass
from typing import Optional, Tuple

import psutil

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QIcon, QPixmap, QAction
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QSystemTrayIcon, QMenu

import win32gui
import win32con

APP_NAME = "UltraMeter"
REFRESH_MS = 1000   # set 500 for ~0.5s updates
MARGIN_PX = 2
W, H = 230, 26

# ====== persistence ======
def appdata_dir() -> str:
    p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    os.makedirs(p, exist_ok=True)
    return p

SETTINGS_PATH = os.path.join(appdata_dir(), "settings.json")

def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(d: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

def asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)

def exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)

# ====== autostart (HKCU\Run) ======
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = APP_NAME

def get_autostart() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            _val, _t = winreg.QueryValueEx(k, RUN_VALUE)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False

def set_autostart(enable: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, f'"{exe_path()}"')
            else:
                try:
                    winreg.DeleteValue(k, RUN_VALUE)
                except FileNotFoundError:
                    pass
    except OSError:
        pass

# ====== taskbar tray geometry ======
def get_tray_rect() -> Optional[Tuple[int, int, int, int]]:
    tray = win32gui.FindWindow("Shell_TrayWnd", None)
    if not tray: return None
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

# ====== units / coloring ======
UNITS_MODE = "bits"   # "bits" or "bytes"
FORCE_UNIT = None     # e.g., "MB/s", "Kbps", etc., or None for auto

def format_rate(bytes_per_sec: float, mode: str="bits", force_unit: Optional[str]=None) -> str:
    if mode == "bytes":
        value = bytes_per_sec
        units = ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]
        step = 1024.0
    else:
        value = bytes_per_sec * 8.0
        units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"]
        step = 1000.0

    if force_unit and force_unit in units:
        idx = units.index(force_unit)
        scaled = value / (step ** idx)
        return _fmt_value(scaled) + f" {force_unit}"

    idx = 0
    while value >= step and idx < len(units) - 1:
        value /= step
        idx += 1
    return _fmt_value(value) + f" {units[idx]}"

def _fmt_value(v: float) -> str:
    if v >= 100: return f"{v:.0f}"
    if v >= 10:  return f"{v:.1f}"
    if v >= 1:   return f"{v:.2f}"
    return f"{v:.2f}" if v > 0 else "0"

def color_for_mbps(mbps: float) -> str:
    if mbps < 5:   return "#46BE5A"
    if mbps < 50:  return "#FFAA28"
    return "#E64646"

@dataclass
class Snapshot:
    sent: int
    recv: int
    ts: float

# ====== UI: strip ======
class CornerStrip(QWidget):
    def __init__(self, app_icon: QIcon, up_pix: QPixmap, down_pix: QPixmap):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowIcon(app_icon)

        self.lbl_down_icon = QLabel();  self.lbl_down_icon.setPixmap(down_pix)
        self.lbl_down = QLabel("↓ …")
        self.lbl_sep = QLabel(" | ");   self.lbl_sep.setStyleSheet("color:#8a8a8a;")
        self.lbl_up_icon = QLabel();    self.lbl_up_icon.setPixmap(up_pix)
        self.lbl_up = QLabel("↑ …")

        for lbl in (self.lbl_down, self.lbl_up):
            f = QFont("Segoe UI", 9); f.setBold(True); lbl.setFont(f)
            lbl.setStyleSheet("color:white;")

        self.btn_pin = QLabel()  # pin toggle
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(6)
        lay.addWidget(self.lbl_down_icon)
        lay.addWidget(self.lbl_down)
        lay.addWidget(self.lbl_sep)
        lay.addWidget(self.lbl_up_icon)
        lay.addWidget(self.lbl_up)
        lay.addStretch()
        lay.addWidget(self.btn_pin)

        self.resize(W, H)

        self.click_through = True
        self._drag: Optional[QPoint] = None

        # pin icons (optional)
        self.pin_off = QPixmap(asset_path("pin_off.png")) if os.path.exists(asset_path("pin_off.png")) else None
        self.pin_on  = QPixmap(asset_path("pin_on.png"))  if os.path.exists(asset_path("pin_on.png"))  else None
        self._update_pin_icon()
        self.btn_pin.mousePressEvent = self._toggle_pin_click

        # shortcuts
        QShortcut(QKeySequence("Ctrl+Shift+L"), self, activated=self.toggle_lock)
        QShortcut(QKeySequence("Ctrl+Shift+U"), self, activated=self.toggle_units)

        # restore persisted state
        st = load_settings()
        if "pos" in st:
            self.move(st["pos"][0], st["pos"][1])
        else:
            self.snap_to_tray()
        if "locked" in st:
            self.set_locked(bool(st["locked"]))
        else:
            self.set_locked(True)

    # ----- behavior -----
    def set_locked(self, locked: bool):
        self.click_through = locked
        self._apply_click_through(self.click_through)
        self._update_pin_icon()
        self._persist()

    def toggle_lock(self):
        self.set_locked(not self.click_through)

    def _toggle_pin_click(self, _e):
        self.toggle_lock()

    def _update_pin_icon(self):
        if self.click_through:
            if self.pin_on:  self.btn_pin.setPixmap(self.pin_on)
            else:            self.btn_pin.setText("📌")
            self.btn_pin.setToolTip("Pinned (click to unpin and drag)")
        else:
            if self.pin_off: self.btn_pin.setPixmap(self.pin_off)
            else:            self.btn_pin.setText("📍")
            self.btn_pin.setToolTip("Unpinned (drag me, then click to pin)")

    def _apply_click_through(self, enable: bool):
        hwnd = int(self.winId())
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enable:
            ex |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
        else:
            ex &= ~(win32con.WS_EX_TRANSPARENT)
            ex |= win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)

    def toggle_units(self):
        global UNITS_MODE
        UNITS_MODE = "bytes" if UNITS_MODE == "bits" else "bits"
        st = load_settings(); st["units"] = UNITS_MODE; save_settings(st)

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
        self._persist()

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
        else:
            l,t,r,b = rect
            screen = QApplication.primaryScreen().geometry()
            x = r - self.width() - MARGIN_PX
            y = t - self.height() - MARGIN_PX
            if abs(t - screen.top()) < 10:  y = b + MARGIN_PX
            if abs(l - screen.left()) < 10: x = r + MARGIN_PX; y = b - self.height() - MARGIN_PX
            if abs(r - screen.right()) < 10:x = l - self.width() - MARGIN_PX; y = b - self.height() - MARGIN_PX
            self.move(x, y)
        self._persist()

    def _persist(self):
        st = load_settings()
        st["pos"] = [self.x(), self.y()]
        st["locked"] = self.click_through
        save_settings(st)

# ====== app ======
class App(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)

        app_icon = QIcon(asset_path("app.ico")) if os.path.exists(asset_path("app.ico")) else QIcon()
        up_pix = QPixmap(asset_path("upload.png")) if os.path.exists(asset_path("upload.png")) else QPixmap()
        down_pix = QPixmap(asset_path("download.png")) if os.path.exists(asset_path("download.png")) else QPixmap()

        self.strip = CornerStrip(app_icon, up_pix, down_pix)
        self.strip.show()

        self.tray = QSystemTrayIcon(app_icon if not app_icon.isNull() else QIcon())
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()

        dock_act = QAction("Dock to right corner")
        dock_act.triggered.connect(self.strip.snap_to_tray)
        menu.addAction(dock_act)

        self.act_show_hide = QAction("Hide Meter")
        self.act_show_hide.triggered.connect(self.toggle_strip)
        menu.addAction(self.act_show_hide)

        self.act_pin = QAction("Unpin (make draggable)")
        self.act_pin.triggered.connect(self.strip.toggle_lock)
        menu.addAction(self.act_pin)

        self.act_units = QAction("Units: bits / bytes")
        self.act_units.triggered.connect(self.strip.toggle_units)
        menu.addAction(self.act_units)

        menu.addSeparator()

        self.act_autostart = QAction("Start with Windows")
        self.act_autostart.setCheckable(True)
        self.act_autostart.setChecked(get_autostart())
        self.act_autostart.toggled.connect(lambda checked: set_autostart(checked))
        menu.addAction(self.act_autostart)

        menu.addSeparator()

        quit_act = QAction("Quit")
        quit_act.triggered.connect(self.quit_app)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        # Only toggle on **double-click** to avoid accidental hides from click-through
        self.tray.activated.connect(self.tray_click)
        self.tray.show()

        self.prev: Optional[Snapshot] = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)

        # restore units mode
        st = load_settings()
        if st.get("units") in ("bits", "bytes"):
            global UNITS_MODE
            UNITS_MODE = st["units"]

    def tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_strip()

    def toggle_strip(self):
        if self.strip.isVisible():
            self.strip.hide()
            self.act_show_hide.setText("Show Meter")
        else:
            self.strip.show()
            self.act_show_hide.setText("Hide Meter")

    def quit_app(self):
        self.strip._persist()
        self.tray.hide()
        self.quit()

    def refresh(self):
        c = psutil.net_io_counters(pernic=False)
        now = time.time()
        if self.prev is None:
            self.prev = Snapshot(c.bytes_sent, c.bytes_recv, now)
            return

        dt = max(1e-6, now - self.prev.ts)
        up_Bps = (c.bytes_sent - self.prev.sent) / dt
        dn_Bps = (c.bytes_recv - self.prev.recv) / dt

        up_Mbps = (up_Bps * 8.0) / 1_000_000
        dn_Mbps = (dn_Bps * 8.0) / 1_000_000

        up_txt = format_rate(up_Bps, UNITS_MODE, FORCE_UNIT)
        dn_txt = format_rate(dn_Bps, UNITS_MODE, FORCE_UNIT)

        self.strip.lbl_up.setText(f"<span style='color:{color_for_mbps(up_Mbps)};'>↑ {up_txt}</span>")
        self.strip.lbl_down.setText(f"<span style='color:{color_for_mbps(dn_Mbps)};'>↓ {dn_txt}</span>")

        self.prev = Snapshot(c.bytes_sent, c.bytes_recv, now)

def main():
    app = App(sys.argv)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
