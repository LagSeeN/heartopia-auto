"""
ควบคุมเมาส์/คีย์บอร์ด (foreground) สำหรับ Windows ด้วย SendInput
(เสถียรกว่า SetCursorPos/mouse_event และรองรับหลายจอ)

รับพิกัด "หน้าจอจริง" (screen coordinates) แล้วสั่งคลิก

มี failsafe: ถ้าผู้ใช้เลื่อนเมาส์ไปชนมุมซ้ายบนสุด -> หยุดฉุกเฉิน
ถ้า SendInput ถูกบล็อก (เกมรันแบบ Admin) -> โยน InputBlocked เพื่อแจ้งให้รันแบบ Admin
"""
from __future__ import annotations

import ctypes
import random
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui

from .exceptions import FailsafeTriggered, InputBlocked
from .i18n import t

# ---------------------------------------------------------------- SendInput
ULONG_PTR = wintypes.WPARAM  # ขนาดเท่า pointer (64/32 บิตอัตโนมัติ)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]


_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_SendInput.restype = wintypes.UINT
_GetSystemMetrics = ctypes.windll.user32.GetSystemMetrics


def _send(inp: INPUT) -> bool:
    """ส่ง 1 event คืน True ถ้าสำเร็จ (ถ้า 0 = ถูก Windows บล็อก เช่น UIPI)"""
    n = _SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return n == 1


def _abs_xy(x: int, y: int) -> tuple[int, int]:
    """แปลงพิกัดหน้าจอจริง -> ค่า absolute 0..65535 เทียบ virtual desktop"""
    vx = _GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = _GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = max(1, _GetSystemMetrics(SM_CXVIRTUALSCREEN) - 1)
    vh = max(1, _GetSystemMetrics(SM_CYVIRTUALSCREEN) - 1)
    nx = int(round((x - vx) * 65535 / vw))
    ny = int(round((y - vy) * 65535 / vh))
    return nx, ny


def _mouse_event(flags: int, x: int | None = None, y: int | None = None):
    mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    if x is not None and y is not None:
        mi.dx, mi.dy = _abs_xy(x, y)
        mi.dwFlags = flags | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    inp = INPUT(type=INPUT_MOUSE, u=_INPUTunion(mi=mi))
    if not _send(inp):
        raise InputBlocked(t("err.input_blocked_mouse"))


def _key_event(vk: int, up: bool):
    ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    inp = INPUT(type=INPUT_KEYBOARD, u=_INPUTunion(ki=ki))
    if not _send(inp):
        raise InputBlocked(t("err.input_blocked_key"))


# แมปปุ่มที่ใช้บ่อย -> virtual key code
_KEYS = {
    "esc": win32con.VK_ESCAPE,
    "enter": win32con.VK_RETURN,
    "space": win32con.VK_SPACE,
    "tab": win32con.VK_TAB,
}


class InputController:
    def __init__(self, config: dict):
        s = config.get("input", {})
        self.delay_min = float(s.get("click_delay_min", 0.06))
        self.delay_max = float(s.get("click_delay_max", 0.18))
        self.instant_move = bool(s.get("instant_move", True))
        self.move_duration = float(s.get("move_duration", 0.25))
        self.settle_before_click = float(s.get("settle_before_click", 0.12))
        self.restore_cursor = bool(s.get("restore_cursor", False))
        self.failsafe = bool(config.get("safety", {}).get("failsafe_corner", True))

    # --- internal ---
    def _rand_delay(self) -> float:
        return random.uniform(self.delay_min, self.delay_max)

    def _check_failsafe(self):
        if self.failsafe:
            x, y = win32api.GetCursorPos()
            if x <= 2 and y <= 2:
                raise FailsafeTriggered(t("err.failsafe"))

    def _move_smooth(self, x: int, y: int):
        """เลื่อนเมาส์ไปเป้าหมาย — พุ่งตรงทันที (instant_move) หรือไล่ทีละสเต็ป"""
        if self.instant_move or self.move_duration <= 0:
            _mouse_event(MOUSEEVENTF_MOVE, x, y)  # พุ่งไปจุดนั้นทันที
            return
        try:
            sx, sy = win32api.GetCursorPos()
        except Exception:
            sx, sy = x, y
        steps = max(1, int(self.move_duration / 0.012))
        for i in range(1, steps + 1):
            t = i / steps
            t = 1 - (1 - t) ** 2  # ease-out
            cx = int(sx + (x - sx) * t)
            cy = int(sy + (y - sy) * t)
            _mouse_event(MOUSEEVENTF_MOVE, cx, cy)
            time.sleep(self.move_duration / steps)

    # --- public ---
    def click(self, pos: tuple[int, int], jitter: int = 2):
        """คลิกซ้ายที่พิกัดหน้าจอจริง pos=(x,y)"""
        self._check_failsafe()
        try:
            old = win32api.GetCursorPos()
        except Exception:
            old = None
        x = pos[0] + random.randint(-jitter, jitter)
        y = pos[1] + random.randint(-jitter, jitter)
        self._move_smooth(x, y)
        # หยุดนิ่งให้เมาส์ถึงเป้าหมายจริงก่อน แล้วค่อยกด (กันคลิกตอนเมาส์ยังไม่ถึง)
        time.sleep(self.settle_before_click + self._rand_delay())
        _mouse_event(MOUSEEVENTF_LEFTDOWN, x, y)
        time.sleep(random.uniform(0.04, 0.09))
        _mouse_event(MOUSEEVENTF_LEFTUP, x, y)
        time.sleep(self._rand_delay())
        if self.restore_cursor and old:
            _mouse_event(MOUSEEVENTF_MOVE, old[0], old[1])

    def tap(self, pos: tuple[int, int], jitter: int = 1):
        """คลิกเร็ว (สำหรับโหมดหลายเตา) — พุ่งไปจุดแล้วกดทันที ไม่หน่วง/ไม่คืนเมาส์
        เร็วระดับเดียวกับบอท auto-tap ทั่วไป (~10-20ms ต่อคลิก)"""
        self._check_failsafe()
        x = pos[0] + random.randint(-jitter, jitter)
        y = pos[1] + random.randint(-jitter, jitter)
        self._move_smooth(x, y)            # instant_move = พุ่งไปจุดนั้นทันที
        _mouse_event(MOUSEEVENTF_LEFTDOWN, x, y)
        time.sleep(0.012)
        _mouse_event(MOUSEEVENTF_LEFTUP, x, y)

    def drag(self, start: tuple[int, int], end: tuple[int, int]):
        """ลากจาก start ไป end (พิกัดหน้าจอจริง) — ใช้กับ slider เช่นปรับไฟ"""
        self._check_failsafe()
        try:
            old = win32api.GetCursorPos()
        except Exception:
            old = None
        self._move_smooth(*start)
        time.sleep(self._rand_delay())
        _mouse_event(MOUSEEVENTF_LEFTDOWN, *start)
        time.sleep(0.1)
        self._move_smooth(*end)
        time.sleep(0.1)
        _mouse_event(MOUSEEVENTF_LEFTUP, *end)
        time.sleep(self._rand_delay())
        if self.restore_cursor and old:
            _mouse_event(MOUSEEVENTF_MOVE, old[0], old[1])

    def press(self, key: str):
        """กดปุ่มคีย์บอร์ด เช่น 'esc', 'enter', 'space', 'f'"""
        self._check_failsafe()
        vk = _KEYS.get(key.lower())
        if vk is None:
            if len(key) == 1:
                vk = ord(key.upper())
            else:
                return
        _key_event(vk, up=False)
        time.sleep(random.uniform(0.04, 0.09))
        _key_event(vk, up=True)
        time.sleep(self._rand_delay())


class BackgroundInput:
    """
    ส่งคลิกเข้าหน้าต่างโดยตรงด้วย PostMessage (สำหรับโหมดเบื้องหลัง)
    - ไม่ขยับเมาส์จริง / ไม่ต้องเอาหน้าต่างขึ้นหน้า -> พับจอไปทำอย่างอื่นได้
    - รับพิกัดเป็น "client coordinates" (ตรงกับภาพจาก BitBltCapture)

    ⚠ บางเกม (โดยเฉพาะที่ใช้ DirectInput/Raw Input) อาจไม่รับ message แบบนี้
       ถ้าคลิกแล้วเกมไม่ตอบสนอง ให้ปิดโหมดเบื้องหลัง (กลับไปโหมด foreground)
    """

    def __init__(self, config: dict):
        s = config.get("input", {})
        self.delay_min = float(s.get("click_delay_min", 0.06))
        self.delay_max = float(s.get("click_delay_max", 0.18))

    @staticmethod
    def _lparam(x: int, y: int) -> int:
        return (int(y) << 16) | (int(x) & 0xFFFF)

    def click(self, hwnd: int, point: tuple[int, int]):
        lp = self._lparam(int(point[0]), int(point[1]))
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lp)
        time.sleep(0.02)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.03, 0.08))
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
        time.sleep(random.uniform(self.delay_min, self.delay_max))
