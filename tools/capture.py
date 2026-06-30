"""
Calibration / template capture tool

Crops button/UI images from the live game screen and saves them as .png files in
assets/templates/. The bot uses these to locate things on screen.

Usage (run from the project folder):
    .venv\\Scripts\\python.exe -m tools.capture

Steps:
  1. Pick the game window from the list
  2. The tool captures one screenshot of the game
  3. Drag the mouse over the button/icon you want, press ENTER to confirm (ESC = cancel)
  4. Type a file name (e.g. cook_start) -> saved as assets/templates/cook_start.png
  5. Repeat as needed; type q to quit
"""
from __future__ import annotations

import os
import sys

# Make the console UTF-8 safe (avoid UnicodeEncodeError on Windows cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Set DPI awareness before importing the rest, so coordinates match the bot
import ctypes
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

import cv2
import numpy as np
from mss import mss

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import window as win  # noqa: E402

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "assets", "templates")

SUGGESTED = [
    "stove          (the STOVE in the world view — click it to OPEN the menu) [required]",
    "cook_start     (the 'Cook' button in the menu, the blue/green one)       [required]",
    "heat_adjust    (the 'adjust heat' button/icon)    [required]",
    "cook_done      (the collect-food / tap-to-continue button) [required]",
    "cook_again     (the 'Cook again' button, if any)  [optional]",
]
print_note = ("Multi-stove auto-tap: the bot clicks EVERY spot matching these templates, "
              "so it handles several stoves at once and presses heat-adjust automatically.")


def choose_window() -> int:
    wins = win.list_windows()
    print("\n=== Open windows ===")
    for i, (h, title) in enumerate(wins):
        print(f"  [{i}] {title}   (hwnd {h})")
    guess = win.find_window(["Heartopia", "心动小镇", "TapTap"])
    default_idx = next((i for i, (h, _) in enumerate(wins) if h == guess), 0)
    raw = input(f"\nSelect the game window number [{default_idx}]: ").strip()
    idx = int(raw) if raw else default_idx
    return wins[idx][0]


def grab_window(hwnd: int) -> np.ndarray:
    win.focus_window(hwnd)
    import time
    time.sleep(0.4)
    region = win.get_capture_region(hwnd, use_client_area=True)
    with mss() as sct:
        shot = sct.grab(region)
    return np.asarray(shot)[:, :, :3]


def main():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    print("=" * 60)
    print(" Heartopia Auto — template capture tool")
    print("=" * 60)
    print("\n" + print_note)
    print("\nRecommended templates to capture for cooking:")
    for s in SUGGESTED:
        print("   -", s)

    hwnd = choose_window()
    print(f"\nSelected: {win.get_title(hwnd)}")

    while True:
        cmd = input("\nPress ENTER to capture the game screen (or type q to quit): ").strip().lower()
        if cmd == "q":
            break
        try:
            frame = grab_window(hwnd)
        except Exception as e:
            print(f"Capture failed: {e}")
            continue

        print("→ Drag over the area you want in the 'Select ROI' window, then press ENTER (ESC = cancel)")
        win_name = "Select ROI - drag then press ENTER"
        roi = cv2.selectROI(win_name, frame, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()
        x, y, w, h = roi
        if w == 0 or h == 0:
            print("Crop cancelled")
            continue
        crop = frame[y:y + h, x:x + w]

        name = input("Name this template (e.g. cook_start): ").strip()
        if not name:
            print("No name given — skipped")
            continue
        if not name.lower().endswith(".png"):
            name += ".png"
        out = os.path.join(TEMPLATES_DIR, name)
        cv2.imwrite(out, crop)
        print(f"✓ Saved: {out}  (size {w}x{h})")

    print("\nDone. All templates are in:", TEMPLATES_DIR)


if __name__ == "__main__":
    main()
