"""
จัดการหน้าต่างเกม (Windows):
- ค้นหา/เลือกหน้าต่าง
- หาพิกัดพื้นที่ client บนหน้าจอจริง (สำหรับ capture + คลิก)
- ดึงหน้าต่างขึ้นมา foreground

หมายเหตุเรื่อง DPI: ต้องเรียก enable_dpi_awareness() ตอนเริ่มโปรแกรม (ใน run.py)
ก่อน import อย่างอื่น เพื่อให้พิกัดของ GetWindowRect / SetCursorPos / mss ตรงกันหมด
"""
from __future__ import annotations

import ctypes
import time

import win32api
import win32con
import win32gui
import win32process

from .exceptions import WindowNotFound
from .i18n import t


def enable_dpi_awareness() -> None:
    """บอก Windows ว่าโปรแกรมนี้รู้เรื่อง DPI เอง เพื่อให้พิกัดเป็น physical pixel ตรงกันทุกที่"""
    try:
        # PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def list_windows() -> list[tuple[int, str]]:
    """คืนรายการหน้าต่างที่มองเห็นได้ทั้งหมด -> [(hwnd, title), ...]"""
    results: list[tuple[int, str]] = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title and title.strip():
            results.append((hwnd, title))

    win32gui.EnumWindows(_cb, None)
    return results


def find_window(title_keywords: list[str]) -> int | None:
    """หา hwnd ตัวแรกที่ title มีคำใดคำหนึ่งใน keywords (ไม่สนตัวพิมพ์)"""
    keys = [k.lower() for k in title_keywords]
    for hwnd, title in list_windows():
        t = title.lower()
        if any(k in t for k in keys):
            return hwnd
    return None


def get_title(hwnd: int) -> str:
    return win32gui.GetWindowText(hwnd)


def is_valid(hwnd: int) -> bool:
    return bool(hwnd) and win32gui.IsWindow(hwnd)


def get_capture_region(hwnd: int, use_client_area: bool = True) -> dict:
    """
    คืน region สำหรับ capture เป็น dict {left, top, width, height} (พิกัดบนหน้าจอจริง)
    พร้อม origin ที่ใช้แปลงพิกัดในภาพ -> พิกัดหน้าจอเวลาคลิก
    """
    if not is_valid(hwnd):
        raise WindowNotFound(t("err.window_gone"))

    if use_client_area:
        # พื้นที่ภายใน (ไม่รวมขอบ/title bar)
        l, t, r, b = win32gui.GetClientRect(hwnd)  # (0,0,w,h)
        ox, oy = win32gui.ClientToScreen(hwnd, (l, t))
        width, height = r - l, b - t
        return {"left": ox, "top": oy, "width": width, "height": height}
    else:
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return {"left": l, "top": t, "width": r - l, "height": b - t}


def get_largest_child(hwnd: int) -> tuple[int | None, int]:
    """หา child window ที่ใหญ่ที่สุดของ hwnd (เกมที่ฝัง engine มักมี child เป็นพื้นผิว render/รับคลิก)"""
    best = [None, 0]

    def _cb(child, _):
        try:
            l, t, r, b = win32gui.GetClientRect(child)
            area = (r - l) * (b - t)
            if area > best[1]:
                best[0], best[1] = child, area
        except Exception:
            pass

    try:
        win32gui.EnumChildWindows(hwnd, _cb, None)
    except Exception:
        pass
    return best[0], best[1]


def resolve_target_hwnd(hwnd: int) -> int:
    """
    คืน hwnd ที่ควรใช้ "ส่งคลิก (PostMessage)" ในโหมดเบื้องหลัง
    ถ้ามี child window ที่ใหญ่เกือบเท่าพื้นที่ทั้งหมด -> ใช้ child นั้น (เกมหลายตัวรับคลิกที่ child)
    ไม่งั้นใช้ hwnd เดิม
    """
    try:
        l, t, r, b = win32gui.GetClientRect(hwnd)
        parent_area = (r - l) * (b - t)
    except Exception:
        return hwnd
    child, area = get_largest_child(hwnd)
    if child and parent_area > 0 and area >= parent_area * 0.7:
        return child
    return hwnd


def focus_window(hwnd: int) -> None:
    """ดึงหน้าต่างเกมขึ้นมาเป็น foreground แบบทนทาน (ใช้ trick AttachThreadInput)"""
    if not is_valid(hwnd):
        raise WindowNotFound(t("err.window_gone"))

    if win32gui.IsIconic(hwnd):  # ถ้าย่ออยู่ ให้คืนขนาด
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)

    if win32gui.GetForegroundWindow() == hwnd:
        return

    cur_thread = win32api.GetCurrentThreadId()
    target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
    attached = False
    try:
        if cur_thread != target_thread:
            win32process.AttachThreadInput(cur_thread, target_thread, True)
            attached = True
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # fallback: กด ALT หลอกๆ เพื่อปลดล็อก SetForegroundWindow ของ Windows
        try:
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    finally:
        if attached:
            try:
                win32process.AttachThreadInput(cur_thread, target_thread, False)
            except Exception:
                pass
    time.sleep(0.15)
