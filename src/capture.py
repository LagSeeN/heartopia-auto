"""
จับภาพหน้าต่างเกมด้วย mss (เร็ว)

หมายเหตุ: instance ของ mss ใช้ได้กับ thread เดียวเท่านั้น
ดังนั้นให้สร้าง GameCapture ภายใน thread ที่ทำงานจริง (worker thread ของ task)
"""
from __future__ import annotations

import numpy as np
import win32gui
import win32ui
from ctypes import windll
from mss import mss

from . import window as win
from .exceptions import WindowNotFound
from .i18n import t

PW_CLIENTONLY = 1
PW_RENDERFULLCONTENT = 2  # Windows 8.1+ จับเนื้อหาที่ render ด้วย DWM/GPU ได้


class GameCapture:
    def __init__(self, hwnd: int, use_client_area: bool = True):
        self.hwnd = hwnd
        self.use_client_area = use_client_area
        self._sct = mss()

    def grab(self) -> tuple[np.ndarray, tuple[int, int]]:
        """
        จับภาพ ณ ตอนนี้ คืน (frame_bgr, origin)
        - frame_bgr: numpy array รูปแบบ BGR (เข้ากับ OpenCV)
        - origin: (left, top) บนหน้าจอจริง ใช้แปลงพิกัดในภาพ -> พิกัดคลิก
        """
        region = win.get_capture_region(self.hwnd, self.use_client_area)
        shot = self._sct.grab(region)
        # mss คืน BGRA -> ตัด alpha เหลือ BGR
        frame = np.asarray(shot)[:, :, :3]
        return frame, (region["left"], region["top"])

    def close(self):
        try:
            self._sct.close()
        except Exception:
            pass


class BitBltCapture:
    """
    จับภาพหน้าต่างแบบ "เบื้องหลัง" ด้วย PrintWindow
    ข้อดี: หน้าต่างเกมไม่ต้องอยู่หน้าสุด (พับจอ/สลับไปทำอย่างอื่นได้)
    ข้อจำกัด: ถ้า "ย่อ (minimize)" หน้าต่าง บาง engine จะจับได้เป็นจอดำ
             -> ปล่อยหน้าต่างเปิดไว้ (อยู่ข้างหลังได้) ดีกว่าย่อ
    คืนพิกัดเป็น client area เสมอ เพื่อให้ตรงกับ PostMessage (BackgroundInput)
    """

    def __init__(self, hwnd: int, use_client_area: bool = True):
        self.hwnd = hwnd

    def grab(self) -> tuple[np.ndarray, tuple[int, int]]:
        hwnd = self.hwnd
        if not win.is_valid(hwnd):
            raise WindowNotFound(t("err.window_gone"))
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        w, h = cr - cl, cb - ct
        if w <= 0 or h <= 0:
            raise WindowNotFound(t("err.window_zero"))

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bmp)
        try:
            windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(),
                                      PW_CLIENTONLY | PW_RENDERFULLCONTENT)
            bmpstr = bmp.GetBitmapBits(True)
            frame = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))[:, :, :3].copy()
        finally:
            win32gui.DeleteObject(bmp.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        return frame, (0, 0)

    def close(self):
        pass
