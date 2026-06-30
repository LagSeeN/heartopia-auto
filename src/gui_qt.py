"""
หน้าต่างควบคุมแบบ Fluent Design (เหมือน ok-nte) ด้วย PySide6 + PyQt-Fluent-Widgets

- มี sidebar นำทาง (Control / Settings)
- การ์ด, ปุ่มโค้งมน, สวิตช์, dark/light/auto theme
- ฟีเจอร์เหมือนเดิม: เลือกหน้าต่างเกม, เลือกงาน+ตั้งค่า, Start/Stop, ทดสอบการตรวจจับ, log, 2 ภาษา

ถ้า import ไม่ได้ (เช่นไม่มี PySide6) run.py จะ fallback ไปใช้ gui.py (Tkinter) อัตโนมัติ
"""
from __future__ import annotations

import os
import queue
import threading
import time

import cv2
import win32api
from PySide6.QtCore import Qt, QObject, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            DoubleSpinBox, FluentIcon as FIF, FluentWindow,
                            InfoBar, InfoBarPosition, NavigationItemPosition,
                            PrimaryPushButton, PushButton, SpinBox, StrongBodyLabel,
                            SubtitleLabel, SwitchButton, TextEdit, Theme, TitleLabel,
                            setTheme, setThemeColor)

from . import window as win
from .bot import Bot
from .exceptions import BotStopped, FailsafeTriggered, InputBlocked, WindowNotFound
from .i18n import LANGUAGES, get_language, set_language, t
from .tasks import get_all_tasks

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "screenshots")
VK_F9 = 0x78
THEME_CODES = ["auto", "dark", "light"]


class _Bridge(QObject):
    """สะพานส่งสัญญาณจาก worker thread -> main thread (Qt signal ปลอดภัยข้าม thread)"""
    log = Signal(str)
    finished = Signal()


def _card(title: str) -> tuple[CardWidget, QVBoxLayout, StrongBodyLabel]:
    card = CardWidget()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(10)
    header = StrongBodyLabel(title)
    lay.addWidget(header)
    return card, lay, header


class MainWindow(FluentWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config_data = config
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._windows: list[tuple[int, str]] = []
        self._running = False

        self.bridge = _Bridge()
        self.bridge.log.connect(self._append_log)
        self.bridge.finished.connect(lambda: self._set_running(False))

        self.tasks = get_all_tasks(self.config_data)

        self._build_control_interface()
        self._build_settings_interface()

        self.nav_control = self.addSubInterface(self.control, FIF.PLAY, t("nav.control"))
        self.nav_settings = self.addSubInterface(self.settings, FIF.SETTING, t("nav.settings"),
                                                 NavigationItemPosition.BOTTOM)

        self.resize(820, 720)
        self.setMinimumSize(700, 600)
        self._retranslate()
        self._refresh_windows(auto_select=True)
        self._check_admin_hint()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_hotkey)
        self._timer.start(60)

    # ----------------------------------------------------------------- build UI
    def _build_control_interface(self):
        self.control = QWidget()
        self.control.setObjectName("controlInterface")
        root = QVBoxLayout(self.control)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(14)

        self.lbl_title = TitleLabel("Heartopia Auto")
        self.lbl_subtitle = CaptionLabel("")
        root.addWidget(self.lbl_title)
        root.addWidget(self.lbl_subtitle)

        # --- card: game window ---
        card_win, lay_win, self.hdr_win = _card("")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.cmb_window = ComboBox()
        self.cmb_window.setMinimumWidth(420)
        self.btn_refresh = PushButton(FIF.SYNC, "")
        self.btn_refresh.clicked.connect(lambda: self._refresh_windows(True))
        row.addWidget(self.cmb_window, 1)
        row.addWidget(self.btn_refresh)
        lay_win.addLayout(row)
        root.addWidget(card_win)

        # --- card: task + settings ---
        card_task, lay_task, self.hdr_task = _card("")
        self.cmb_task = ComboBox()
        self.cmb_task.addItems([t(tk.name_key) for tk in self.tasks])
        self.cmb_task.setCurrentIndex(0)
        self.cmb_task.currentIndexChanged.connect(self._update_task_desc)
        lay_task.addWidget(self.cmb_task)
        self.lbl_desc = BodyLabel("")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: gray;")
        lay_task.addWidget(self.lbl_desc)

        cook = self.config_data.get("cooking", {})
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.lbl_repeat = BodyLabel("")
        self.spn_repeat = SpinBox()
        self.spn_repeat.setRange(0, 100000)
        self.spn_repeat.setValue(int(cook.get("repeat", 0)))
        self.lbl_scan = BodyLabel("")
        self.spn_scan = DoubleSpinBox()
        self.spn_scan.setRange(0.0, 5.0)
        self.spn_scan.setSingleStep(0.05)
        self.spn_scan.setDecimals(2)
        self.spn_scan.setValue(float(cook.get("scan_delay", 0.1)))
        grid.addWidget(self.lbl_repeat, 0, 0)
        grid.addWidget(self.spn_repeat, 0, 1)
        grid.addWidget(self.lbl_scan, 0, 2)
        grid.addWidget(self.spn_scan, 0, 3)
        grid.setColumnStretch(4, 1)
        lay_task.addLayout(grid)

        row_bg = QHBoxLayout()
        self.lbl_bg = BodyLabel("")
        self.sw_bg = SwitchButton()
        self.sw_bg.setChecked(bool(self.config_data.get("runtime", {}).get("background_mode", False)))
        row_bg.addWidget(self.sw_bg)
        row_bg.addWidget(self.lbl_bg)
        row_bg.addStretch(1)
        lay_task.addLayout(row_bg)
        root.addWidget(card_task)

        # --- controls row ---
        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        self.btn_start = PrimaryPushButton(FIF.PLAY, "")
        self.btn_start.clicked.connect(self._start)
        self.btn_stop = PushButton(FIF.CANCEL, "")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        self.btn_detect = PushButton(FIF.SEARCH, "")
        self.btn_detect.clicked.connect(self._detect_test)
        self.lbl_status = BodyLabel("")
        ctl.addWidget(self.btn_start)
        ctl.addWidget(self.btn_stop)
        ctl.addWidget(self.btn_detect)
        ctl.addStretch(1)
        ctl.addWidget(self.lbl_status)
        root.addLayout(ctl)

        # --- log ---
        self.txt_log = TextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(200)
        root.addWidget(self.txt_log, 1)

        self.lbl_emergency = CaptionLabel("")
        self.lbl_emergency.setStyleSheet("color: #c0392b;")
        root.addWidget(self.lbl_emergency)

    def _build_settings_interface(self):
        self.settings = QWidget()
        self.settings.setObjectName("settingsInterface")
        root = QVBoxLayout(self.settings)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(14)
        self.lbl_settings_title = TitleLabel("")
        root.addWidget(self.lbl_settings_title)

        # appearance card: language + theme
        card_app, lay_app, self.hdr_appearance = _card("")
        row_lang = QHBoxLayout()
        self.lbl_lang = BodyLabel("")
        self.cmb_lang = ComboBox()
        self.cmb_lang.addItems([name for name, _ in LANGUAGES])
        cur = get_language()
        self._lang_codes = [code for _, code in LANGUAGES]
        self.cmb_lang.setCurrentIndex(self._lang_codes.index(cur) if cur in self._lang_codes else 0)
        self.cmb_lang.currentIndexChanged.connect(self._on_lang_change)
        row_lang.addWidget(self.lbl_lang)
        row_lang.addStretch(1)
        row_lang.addWidget(self.cmb_lang)
        lay_app.addLayout(row_lang)

        row_theme = QHBoxLayout()
        self.lbl_theme = BodyLabel("")
        self.cmb_theme = ComboBox()
        self.cmb_theme.addItems([t("theme.auto"), t("theme.dark"), t("theme.light")])
        cur_theme = self.config_data.get("theme", "auto")
        self.cmb_theme.setCurrentIndex(THEME_CODES.index(cur_theme) if cur_theme in THEME_CODES else 0)
        self.cmb_theme.currentIndexChanged.connect(self._on_theme_change)
        row_theme.addWidget(self.lbl_theme)
        row_theme.addStretch(1)
        row_theme.addWidget(self.cmb_theme)
        lay_app.addLayout(row_theme)
        root.addWidget(card_app)

        # about / safety card
        card_about, lay_about, self.hdr_about = _card("")
        self.lbl_about = BodyLabel("")
        self.lbl_about.setWordWrap(True)
        lay_about.addWidget(self.lbl_about)
        root.addWidget(card_about)
        root.addStretch(1)

    # ----------------------------------------------------------------- i18n
    def _retranslate(self):
        self.setWindowTitle(t("win.title"))
        self.lbl_title.setText(t("win.title"))
        self.lbl_subtitle.setText(t("app.subtitle"))
        self.hdr_win.setText(t("frame.window"))
        self.btn_refresh.setText(t("btn.refresh"))
        self.hdr_task.setText(t("frame.task"))
        self.lbl_repeat.setText(t("lbl.repeat"))
        self.lbl_scan.setText(t("lbl.scan_delay"))
        self.lbl_bg.setText(t("chk.background"))
        self.sw_bg.setOnText(t("switch.on"))
        self.sw_bg.setOffText(t("switch.off"))
        self.btn_start.setText(t("btn.start"))
        self.btn_stop.setText(t("btn.stop"))
        self.btn_detect.setText(t("btn.detect"))
        self.lbl_emergency.setText(t("lbl.emergency"))
        self.lbl_settings_title.setText(t("nav.settings"))
        self.hdr_appearance.setText(t("settings.appearance"))
        self.lbl_lang.setText(t("lbl.lang"))
        self.lbl_theme.setText(t("settings.theme"))
        self.hdr_about.setText(t("settings.about"))
        self.lbl_about.setText(t("settings.about_body"))
        # task combobox (เก็บ index เดิม)
        idx = self.cmb_task.currentIndex()
        self.cmb_task.blockSignals(True)
        self.cmb_task.clear()
        self.cmb_task.addItems([t(tk.name_key) for tk in self.tasks])
        self.cmb_task.setCurrentIndex(max(0, idx))
        self.cmb_task.blockSignals(False)
        self._update_task_desc()
        self._set_running(self._running)
        for item, key in ((getattr(self, "nav_control", None), "nav.control"),
                          (getattr(self, "nav_settings", None), "nav.settings")):
            try:
                if item is not None:
                    item.setText(t(key))
            except Exception:
                pass

    def _on_lang_change(self, idx: int):
        if 0 <= idx < len(self._lang_codes):
            set_language(self._lang_codes[idx])
            self.config_data["language"] = self._lang_codes[idx]
            self._retranslate()

    def _on_theme_change(self, idx: int):
        code = THEME_CODES[idx] if 0 <= idx < len(THEME_CODES) else "auto"
        self.config_data["theme"] = code
        setTheme({"auto": Theme.AUTO, "dark": Theme.DARK, "light": Theme.LIGHT}[code])

    def _update_task_desc(self, *_):
        idx = self.cmb_task.currentIndex()
        if 0 <= idx < len(self.tasks):
            self.lbl_desc.setText(t(self.tasks[idx].desc_key))

    # ----------------------------------------------------------------- windows
    def _refresh_windows(self, auto_select=False):
        self._windows = win.list_windows()
        labels = [f"{title}   ·   hwnd {h}" for h, title in self._windows]
        self.cmb_window.blockSignals(True)
        self.cmb_window.clear()
        self.cmb_window.addItems(labels)
        self.cmb_window.blockSignals(False)
        if not labels:
            return
        target = 0
        if auto_select:
            keys = self.config_data.get("window", {}).get("title_keywords", [])
            hwnd = win.find_window(keys)
            if hwnd:
                for i, (h, _t) in enumerate(self._windows):
                    if h == hwnd:
                        target = i
                        self._append_log(t("log.autodetect", title=win.get_title(hwnd)))
                        break
        self.cmb_window.setCurrentIndex(target)

    def _selected_hwnd(self) -> int | None:
        idx = self.cmb_window.currentIndex()
        if 0 <= idx < len(self._windows):
            return self._windows[idx][0]
        return None

    # ----------------------------------------------------------------- start/stop
    def _apply_config_edits(self):
        self.config_data.setdefault("cooking", {})["repeat"] = int(self.spn_repeat.value())
        self.config_data["cooking"]["scan_delay"] = float(self.spn_scan.value())
        self.config_data.setdefault("runtime", {})["background_mode"] = bool(self.sw_bg.isChecked())

    def _start(self):
        if self._worker and self._worker.is_alive():
            return
        hwnd = self._selected_hwnd()
        if not hwnd or not win.is_valid(hwnd):
            InfoBar.warning("", t("log.select_window_first"), duration=3000,
                            position=InfoBarPosition.TOP, parent=self)
            return
        self._apply_config_edits()
        task = self.tasks[self.cmb_task.currentIndex()]
        self._stop_event.clear()
        self._set_running(True)
        self._append_log(t("log.start_task", task=t(task.name_key)))
        InfoBar.success("", t("info.started"), duration=1500,
                        position=InfoBarPosition.TOP_RIGHT, parent=self)
        self._worker = threading.Thread(target=self._run_task, args=(hwnd, task), daemon=True)
        self._worker.start()

    def _run_task(self, hwnd: int, task):
        bot = None
        log = self.bridge.log.emit
        try:
            bot = Bot(hwnd, self.config_data, self._stop_event, logger=log)
            task.run(bot)
        except BotStopped:
            log(t("log.stopped_user"))
        except FailsafeTriggered as e:
            log(t("log.emergency_stop", msg=e))
        except InputBlocked as e:
            log(t("log.input_blocked", msg=e))
        except WindowNotFound as e:
            log(t("log.window_not_found", msg=e))
        except Exception as e:  # noqa: BLE001
            import traceback
            log(t("log.error", msg=e))
            log(traceback.format_exc())
        finally:
            if bot:
                bot.close()
            self.bridge.finished.emit()

    def _stop(self):
        self._stop_event.set()
        self._append_log(t("log.stopping"))

    def _set_running(self, running: bool):
        self._running = running
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_detect.setEnabled(not running)
        if running:
            self.lbl_status.setText(t("status.running"))
            self.lbl_status.setStyleSheet("color: #e67e22; font-weight: bold;")
        else:
            self.lbl_status.setText(t("status.ready"))
            self.lbl_status.setStyleSheet("color: #2ecc71; font-weight: bold;")

    # ----------------------------------------------------------------- detect test
    def _detect_test(self):
        if self._worker and self._worker.is_alive():
            return
        hwnd = self._selected_hwnd()
        if not hwnd or not win.is_valid(hwnd):
            InfoBar.warning("", t("log.select_window_short"), duration=3000,
                            position=InfoBarPosition.TOP, parent=self)
            return
        self._apply_config_edits()
        threading.Thread(target=self._run_detect_test, args=(hwnd,), daemon=True).start()

    def _run_detect_test(self, hwnd: int):
        log = self.bridge.log.emit
        try:
            log(t("log.detect_header"))
            if not self.config_data.get("runtime", {}).get("background_mode", False):
                win.focus_window(hwnd)
                time.sleep(0.3)
            bot = Bot(hwnd, self.config_data, self._stop_event, logger=log)
            frame = bot.screenshot()
            mean = float(frame.mean())
            log(t("log.captured", w=frame.shape[1], h=frame.shape[0], mean=f"{mean:.1f}"))
            if mean < 3:
                log(t("log.black_warn"))
            matches = bot.vision.find_all_known(frame)
            if not matches:
                log(t("log.no_templates"))
            annotated = frame.copy()
            for m in matches:
                tag = t("tag.found") if m.found else t("tag.notfound")
                log(t("log.detect_row", tag=tag, name=f"{m.name:16s}", score=f"{m.score:.3f}"))
                if m.found:
                    x, y, w, h = m.rect
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(annotated, m.name, (x, max(0, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            out = os.path.join(SCREENSHOT_DIR, f"detect_{int(time.time())}.png")
            cv2.imwrite(out, annotated)
            log(t("log.saved_detect", path=out))
            bot.close()
        except Exception as e:  # noqa: BLE001
            log(t("log.detect_failed", msg=e))

    # ----------------------------------------------------------------- log + hotkey
    def _append_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.txt_log.append(f"[{ts}] {msg}")

    def _poll_hotkey(self):
        if self.config_data.get("safety", {}).get("stop_hotkey_f9", True):
            if win32api.GetAsyncKeyState(VK_F9) & 0x8000:
                if self._worker and self._worker.is_alive() and not self._stop_event.is_set():
                    self._stop()

    def _check_admin_hint(self):
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = 0
        self._append_log(t("log.admin_yes") if is_admin else t("log.admin_no"))

    def closeEvent(self, event):
        self._stop_event.set()
        super().closeEvent(event)


def run_gui(config: dict):
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    theme = config.get("theme", "auto")
    setTheme({"auto": Theme.AUTO, "dark": Theme.DARK, "light": Theme.LIGHT}.get(theme, Theme.AUTO))
    setThemeColor("#ff8c42")  # โทนอุ่น เข้ากับเกมแนว cozy
    w = MainWindow(config)
    w.show()
    app.exec()
