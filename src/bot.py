"""
Bot = ตัวกลางที่รวม capture + vision + input + การตั้งค่า เข้าด้วยกัน
และมี helper ระดับสูงให้ task เรียกใช้ง่ายๆ เช่น find / wait_for / click / sleep

ทุกเมธอดที่รอคอย จะคอยเช็ก stop_event เพื่อให้หยุดได้ทันทีที่ผู้ใช้สั่ง
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

import numpy as np
import win32gui

from . import window as win
from .capture import BitBltCapture, GameCapture
from .exceptions import BotStopped
from .i18n import t
from .input_controller import BackgroundInput, InputController
from .vision import Match, Vision

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "templates")


class Bot:
    def __init__(self, hwnd: int, config: dict,
                 stop_event: threading.Event,
                 logger: Callable[[str], None] | None = None):
        self.hwnd = hwnd
        self.config = config
        self.stop_event = stop_event
        self.log = logger or (lambda msg: print(msg))

        self.background = bool(config.get("runtime", {}).get("background_mode", False))
        self.action_delay = float(config.get("input", {}).get("action_delay", 0.5))
        self.vision = Vision(TEMPLATES_DIR, config)
        self._last_origin = (0, 0)
        self.target_hwnd = hwnd  # hwnd ที่ใช้ส่งคลิก (อาจเป็น child ในโหมดเบื้องหลัง)

        if self.background:
            # โหมดเบื้องหลัง: จับภาพจาก top-level (ครอบคลุม child) แต่ส่งคลิกไปยัง child ที่รับ input
            self.target_hwnd = win.resolve_target_hwnd(hwnd)
            self.capture = BitBltCapture(hwnd, True)
            self.input = None
            self.bg_input = BackgroundInput(config)
            if self.target_hwnd != hwnd:
                self.log(t("bot.bg_child", hwnd=self.target_hwnd))
        else:
            use_client = config.get("window", {}).get("use_client_area", True)
            self.capture = GameCapture(hwnd, use_client)
            self.input = InputController(config)
            self.bg_input = None

    # --- การควบคุมการหยุด ---
    def check_stop(self):
        if self.stop_event.is_set():
            raise BotStopped(t("err.stopped_user"))

    def sleep(self, seconds: float):
        """หน่วงเวลาแบบขัดจังหวะได้ (เช็ก stop ทุก 0.1 วิ)"""
        end = time.time() + seconds
        while time.time() < end:
            self.check_stop()
            time.sleep(min(0.1, max(0.0, end - time.time())))

    # --- การมองเห็น ---
    def screenshot(self) -> np.ndarray:
        frame, origin = self.capture.grab()
        self._last_origin = origin
        return frame

    def find(self, name: str, frame: np.ndarray | None = None,
             threshold: float | None = None) -> Match:
        if frame is None:
            frame = self.screenshot()
        return self.vision.find(frame, name, threshold)

    def exists(self, name: str, threshold: float | None = None) -> bool:
        return self.find(name, threshold=threshold).found

    def wait_for(self, name: str, timeout: float = 15.0, interval: float = 0.4,
                 threshold: float | None = None) -> Match | None:
        """รอจน template ปรากฏ คืน Match ถ้าเจอ / None ถ้าหมดเวลา"""
        end = time.time() + timeout
        while time.time() < end:
            self.check_stop()
            m = self.find(name, threshold=threshold)
            if m.found:
                return m
            time.sleep(interval)
        return None

    def wait_any(self, names: list[str], timeout: float = 15.0,
                 interval: float = 0.4) -> Match | None:
        """รอ template หลายตัวพร้อมกัน คืนตัวแรกที่เจอ"""
        end = time.time() + timeout
        while time.time() < end:
            self.check_stop()
            frame = self.screenshot()
            for name in names:
                m = self.vision.find(frame, name)
                if m.found:
                    return m
            time.sleep(interval)
        return None

    # --- การกระทำ ---
    def _to_screen(self, point: tuple[int, int]) -> tuple[int, int]:
        ox, oy = self._last_origin
        return ox + point[0], oy + point[1]

    def find_all(self, name: str, frame: np.ndarray | None = None,
                 threshold: float | None = None, dedup_distance: int = 30) -> list[Match]:
        if frame is None:
            frame = self.screenshot()
        return self.vision.find_all(frame, name, threshold, dedup_distance)

    def _bg_target(self, point: tuple[int, int]) -> tuple[int, int]:
        """แปลงพิกัดจาก client ของ top-level (ภาพที่จับ) -> client ของ target hwnd (ที่ส่งคลิก)"""
        if self.target_hwnd != self.hwnd:
            sx, sy = win32gui.ClientToScreen(self.hwnd, (int(point[0]), int(point[1])))
            return win32gui.ScreenToClient(self.target_hwnd, (sx, sy))
        return int(point[0]), int(point[1])

    def click_point(self, point: tuple[int, int], delay: float | None = None):
        """คลิกที่พิกัดในภาพ (frame coords) — แบบมีดีเลย์รอ UI (ใช้กับ step ที่ต้องรอ)
        delay = หน่วงหลังคลิก (None = ใช้ action_delay)"""
        self.check_stop()
        if self.background:
            self.bg_input.click(self.target_hwnd, self._bg_target(point))
        else:
            self.input.click(self._to_screen(point))
        d = self.action_delay if delay is None else delay
        if d > 0:
            self.sleep(d)

    def tap_point(self, point: tuple[int, int]):
        """คลิกเร็ว ไม่หน่วง (สำหรับโหมดหลายเตา) — เร็วระดับเดียวกับบอท auto-tap"""
        self.check_stop()
        if self.background:
            self.bg_input.click(self.target_hwnd, self._bg_target(point))
        else:
            self.input.tap(self._to_screen(point))

    def click(self, target, threshold: float | None = None) -> bool:
        """
        คลิกเป้าหมาย:
        - ถ้า target เป็น str = ชื่อ template -> หาแล้วคลิกตรงกลาง
        - ถ้า target เป็น (x, y) = พิกัดในภาพ -> คลิกตรงนั้น
        คืน True ถ้าคลิกสำเร็จ
        """
        self.check_stop()
        if isinstance(target, str):
            m = self.find(target, threshold=threshold)
            if not m.found:
                return False
            point = m.center
        else:
            point = target
        self.click_point(point)
        return True

    def click_when(self, name: str, timeout: float = 15.0,
                   threshold: float | None = None) -> bool:
        """รอจนเจอ template แล้วคลิก"""
        m = self.wait_for(name, timeout=timeout, threshold=threshold)
        if m is None:
            return False
        self.click_point(m.center)
        return True

    def press_key(self, key: str):
        """กดปุ่มคีย์บอร์ด (เช่น 'enter') — ใช้เปิดเมนู/โต้ตอบกับเกม
        หมายเหตุ: โหมดเบื้องหลังยังส่งคีย์ให้เกม Unity ไม่ได้ -> ข้าม"""
        self.check_stop()
        if self.background or not self.input:
            return
        self.input.press(key)
        if self.action_delay > 0:
            self.sleep(self.action_delay)

    def focus(self):
        if self.background:
            return  # โหมดเบื้องหลัง: ไม่ต้องดึงหน้าต่างขึ้นหน้า
        win.focus_window(self.hwnd)

    def close(self):
        self.capture.close()
