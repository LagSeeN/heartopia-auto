"""
Control panel (GUI) built with Tkinter — no extra dependency.

Features:
- pick the game window (auto-detect or choose manually)
- pick a task + quick settings (repeat count / heat adjusts)
- Start / Stop
- "Detect test": capture once and report which templates were found + score
- log box
- language switch (English / ไทย), live
- emergency stop: F9 or shove the mouse into the top-left screen corner
"""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
import win32api

from . import window as win
from .bot import Bot, TEMPLATES_DIR
from .exceptions import BotStopped, FailsafeTriggered, InputBlocked, WindowNotFound
from .i18n import LANGUAGES, get_language, set_language, t
from .tasks import get_all_tasks

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "screenshots")
VK_F9 = 0x78


class App(tk.Tk):
    def __init__(self, config: dict):
        super().__init__()
        self.config_data = config

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._windows: list[tuple[int, str]] = []
        self._running = False

        self._build_ui()
        self._apply_texts()
        self._check_admin_hint()
        self._refresh_windows(auto_select=True)
        self.after(100, self._drain_log)
        self.after(60, self._poll_hotkey)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------- UI
    def _build_ui(self):
        self.geometry("680x680")
        self.minsize(580, 580)
        pad = {"padx": 8, "pady": 4}

        # --- language selector (top) ---
        frm_top = ttk.Frame(self)
        frm_top.pack(fill="x", padx=8, pady=(6, 0))
        self.lbl_lang = ttk.Label(frm_top, text="Language:")
        self.lbl_lang.pack(side="right", padx=(4, 2))
        self._lang_names = [name for name, _ in LANGUAGES]
        self._lang_codes = [code for _, code in LANGUAGES]
        self.cmb_lang = ttk.Combobox(frm_top, state="readonly", width=10, values=self._lang_names)
        cur = get_language()
        self.cmb_lang.current(self._lang_codes.index(cur) if cur in self._lang_codes else 0)
        self.cmb_lang.pack(side="right")
        self.cmb_lang.bind("<<ComboboxSelected>>", lambda e: self._on_lang_change())

        # --- game window ---
        self.frm_win = ttk.LabelFrame(self, text="")
        self.frm_win.pack(fill="x", **pad)
        self.cmb_window = ttk.Combobox(self.frm_win, state="readonly", width=58)
        self.cmb_window.pack(side="left", padx=6, pady=6)
        self.btn_refresh = ttk.Button(self.frm_win, text="",
                                      command=lambda: self._refresh_windows(True))
        self.btn_refresh.pack(side="left", padx=4)

        # --- task + settings ---
        self.frm_task = ttk.LabelFrame(self, text="")
        self.frm_task.pack(fill="x", **pad)

        self.tasks = get_all_tasks(self.config_data)
        self.cmb_task = ttk.Combobox(self.frm_task, state="readonly", width=40,
                                     values=[t(task.name_key) for task in self.tasks])
        self.cmb_task.current(0)
        self.cmb_task.grid(row=0, column=0, columnspan=2, padx=6, pady=6, sticky="w")
        self.cmb_task.bind("<<ComboboxSelected>>", lambda e: self._update_task_desc())
        self.lbl_desc = ttk.Label(self.frm_task, text="", wraplength=620, foreground="#555")
        self.lbl_desc.grid(row=1, column=0, columnspan=4, padx=6, sticky="w")

        cook = self.config_data.get("cooking", {})
        self.lbl_repeat = ttk.Label(self.frm_task, text="")
        self.lbl_repeat.grid(row=2, column=0, padx=6, pady=4, sticky="e")
        self.var_repeat = tk.StringVar(value=str(cook.get("repeat", 0)))
        ttk.Entry(self.frm_task, textvariable=self.var_repeat, width=8).grid(row=2, column=1, sticky="w")
        self.lbl_scan = ttk.Label(self.frm_task, text="")
        self.lbl_scan.grid(row=2, column=2, padx=6, sticky="e")
        self.var_scan = tk.StringVar(value=str(cook.get("scan_delay", 0.3)))
        ttk.Entry(self.frm_task, textvariable=self.var_scan, width=8).grid(row=2, column=3, sticky="w")

        runtime = self.config_data.get("runtime", {})
        self.var_background = tk.BooleanVar(value=bool(runtime.get("background_mode", False)))
        self.chk_bg = ttk.Checkbutton(self.frm_task, text="", variable=self.var_background)
        self.chk_bg.grid(row=3, column=0, columnspan=4, padx=6, pady=(2, 6), sticky="w")

        # --- controls ---
        frm_ctl = ttk.Frame(self)
        frm_ctl.pack(fill="x", **pad)
        self.btn_start = ttk.Button(frm_ctl, text="", command=self._start)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(frm_ctl, text="", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        self.btn_detect = ttk.Button(frm_ctl, text="", command=self._detect_test)
        self.btn_detect.pack(side="left", padx=4)
        self.lbl_status = ttk.Label(frm_ctl, text="", foreground="green")
        self.lbl_status.pack(side="right", padx=8)

        # --- log ---
        self.frm_log = ttk.LabelFrame(self, text="Log")
        self.frm_log.pack(fill="both", expand=True, **pad)
        self.txt_log = tk.Text(self.frm_log, height=16, wrap="word", state="disabled",
                               bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.txt_log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.frm_log, command=self.txt_log.yview)
        sb.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=sb.set)

        self.lbl_emergency = ttk.Label(self, text="", foreground="#a00")
        self.lbl_emergency.pack(pady=2)

    def _apply_texts(self):
        """ใส่/อัปเดตข้อความทุก widget ตามภาษาปัจจุบัน (เรียกตอนเริ่มและตอนสลับภาษา)"""
        self.title(t("win.title"))
        self.lbl_lang.config(text=t("lbl.lang"))
        self.frm_win.config(text=t("frame.window"))
        self.btn_refresh.config(text=t("btn.refresh"))
        self.frm_task.config(text=t("frame.task"))
        self.lbl_repeat.config(text=t("lbl.repeat"))
        self.lbl_scan.config(text=t("lbl.scan_delay"))
        self.chk_bg.config(text=t("chk.background"))
        self.btn_start.config(text=t("btn.start"))
        self.btn_stop.config(text=t("btn.stop"))
        self.btn_detect.config(text=t("btn.detect"))
        self.frm_log.config(text=t("frame.log"))
        self.lbl_emergency.config(text=t("lbl.emergency"))
        # task combobox (เก็บ index เดิมไว้)
        idx = self.cmb_task.current()
        self.cmb_task["values"] = [t(task.name_key) for task in self.tasks]
        if 0 <= idx < len(self.tasks):
            self.cmb_task.current(idx)
        self._update_task_desc()
        self._set_running(self._running)

    def _on_lang_change(self):
        idx = self.cmb_lang.current()
        if 0 <= idx < len(self._lang_codes):
            code = self._lang_codes[idx]
            set_language(code)
            self.config_data["language"] = code
            self._apply_texts()

    def _check_admin_hint(self):
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = 0
        self._log(t("log.admin_yes") if is_admin else t("log.admin_no"))

    def _update_task_desc(self):
        idx = self.cmb_task.current()
        if 0 <= idx < len(self.tasks):
            self.lbl_desc.config(text=t(self.tasks[idx].desc_key))

    # ------------------------------------------------------------- windows
    def _refresh_windows(self, auto_select=False):
        self._windows = win.list_windows()
        labels = [f"{title}    [hwnd {h}]" for h, title in self._windows]
        self.cmb_window["values"] = labels
        if not labels:
            return
        if auto_select:
            keys = self.config_data.get("window", {}).get("title_keywords", [])
            hwnd = win.find_window(keys)
            if hwnd:
                for i, (h, _t) in enumerate(self._windows):
                    if h == hwnd:
                        self.cmb_window.current(i)
                        self._log(t("log.autodetect", title=win.get_title(hwnd)))
                        return
        if self.cmb_window.current() < 0:
            self.cmb_window.current(0)

    def _selected_hwnd(self) -> int | None:
        idx = self.cmb_window.current()
        if 0 <= idx < len(self._windows):
            return self._windows[idx][0]
        return None

    # --------------------------------------------------------------- start/stop
    def _apply_config_edits(self):
        try:
            self.config_data.setdefault("cooking", {})["repeat"] = int(self.var_repeat.get())
            self.config_data["cooking"]["scan_delay"] = float(self.var_scan.get())
        except ValueError:
            self._log(t("log.invalid_number"))
        self.config_data.setdefault("runtime", {})["background_mode"] = bool(self.var_background.get())

    def _start(self):
        if self._worker and self._worker.is_alive():
            return
        hwnd = self._selected_hwnd()
        if not hwnd or not win.is_valid(hwnd):
            self._log(t("log.select_window_first"))
            return
        self._apply_config_edits()
        task = self.tasks[self.cmb_task.current()]
        self._stop_event.clear()
        self._set_running(True)
        self._log(t("log.start_task", task=t(task.name_key)))
        self._worker = threading.Thread(target=self._run_task, args=(hwnd, task), daemon=True)
        self._worker.start()

    def _run_task(self, hwnd: int, task):
        bot = None
        try:
            bot = Bot(hwnd, self.config_data, self._stop_event, logger=self._log)
            task.run(bot)
        except BotStopped:
            self._log(t("log.stopped_user"))
        except FailsafeTriggered as e:
            self._log(t("log.emergency_stop", msg=e))
        except InputBlocked as e:
            self._log(t("log.input_blocked", msg=e))
        except WindowNotFound as e:
            self._log(t("log.window_not_found", msg=e))
        except Exception as e:  # noqa: BLE001
            import traceback
            self._log(t("log.error", msg=e))
            self._log(traceback.format_exc())
        finally:
            if bot:
                bot.close()
            self.after(0, lambda: self._set_running(False))

    def _stop(self):
        self._stop_event.set()
        self._log(t("log.stopping"))

    def _set_running(self, running: bool):
        self._running = running
        self.btn_start.config(state="disabled" if running else "normal")
        self.btn_stop.config(state="normal" if running else "disabled")
        self.lbl_status.config(text=t("status.running") if running else t("status.ready"),
                               foreground="orange" if running else "green")

    # --------------------------------------------------------------- detect test
    def _detect_test(self):
        if self._worker and self._worker.is_alive():
            self._log(t("log.busy_detect"))
            return
        hwnd = self._selected_hwnd()
        if not hwnd or not win.is_valid(hwnd):
            self._log(t("log.select_window_short"))
            return
        self._apply_config_edits()  # ให้ detect ใช้โหมด (เบื้องหลัง/หน้า) ตาม checkbox ปัจจุบัน
        threading.Thread(target=self._run_detect_test, args=(hwnd,), daemon=True).start()

    def _run_detect_test(self, hwnd: int):
        try:
            self._log(t("log.detect_header"))
            if not self.config_data.get("runtime", {}).get("background_mode", False):
                win.focus_window(hwnd)
                time.sleep(0.3)
            bot = Bot(hwnd, self.config_data, self._stop_event, logger=self._log)
            frame = bot.screenshot()
            mean = float(frame.mean())
            self._log(t("log.captured", w=frame.shape[1], h=frame.shape[0], mean=f"{mean:.1f}"))
            if mean < 3:
                self._log(t("log.black_warn"))
            matches = bot.vision.find_all_known(frame)
            if not matches:
                self._log(t("log.no_templates"))
            annotated = frame.copy()
            for m in matches:
                tag = t("tag.found") if m.found else t("tag.notfound")
                self._log(t("log.detect_row", tag=tag, name=f"{m.name:16s}", score=f"{m.score:.3f}"))
                if m.found:
                    x, y, w, h = m.rect
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(annotated, m.name, (x, max(0, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            out = os.path.join(SCREENSHOT_DIR, f"detect_{int(time.time())}.png")
            cv2.imwrite(out, annotated)
            self._log(t("log.saved_detect", path=out))
            bot.close()
        except Exception as e:  # noqa: BLE001
            self._log(t("log.detect_failed", msg=e))

    # --------------------------------------------------------------- log + hotkey
    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self._log_queue.put(f"[{ts}] {msg}")

    def _drain_log(self):
        try:
            while True:
                line = self._log_queue.get_nowait()
                self.txt_log.config(state="normal")
                self.txt_log.insert("end", line + "\n")
                self.txt_log.see("end")
                self.txt_log.config(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def _poll_hotkey(self):
        # F9 = emergency stop (only while running)
        if self.config_data.get("safety", {}).get("stop_hotkey_f9", True):
            if win32api.GetAsyncKeyState(VK_F9) & 0x8000:
                if self._worker and self._worker.is_alive() and not self._stop_event.is_set():
                    self._stop()
        self.after(60, self._poll_hotkey)

    def _on_close(self):
        self._stop_event.set()
        self.destroy()


def run_gui(config: dict):
    App(config).mainloop()
