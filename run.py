"""
จุดเริ่มต้นโปรแกรม Heartopia Auto

รัน:
    .venv\\Scripts\\python.exe run.py
"""
from __future__ import annotations

import os
import sys

# 0) ทำให้ console รองรับภาษาไทย (กัน UnicodeEncodeError บน Windows cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 1) ตั้ง DPI awareness ก่อนเป็นอันดับแรก เพื่อให้พิกัด capture/คลิกตรงกัน
from src.window import enable_dpi_awareness
enable_dpi_awareness()

import yaml  # noqa: E402

from src.i18n import set_language  # noqa: E402

# ใช้ UI แบบ Fluent (เหมือน ok-nte) ถ้ามี PySide6; ถ้าไม่มีก็ fallback ไป Tkinter
try:
    from src.gui_qt import run_gui  # noqa: E402
    _UI = "Fluent (PySide6)"
except Exception as _e:  # noqa: BLE001
    from src.gui import run_gui  # noqa: E402
    _UI = f"Tkinter (PySide6 ไม่พร้อม: {_e})"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def main():
    config = load_config()
    set_language(config.get("language", "en"))
    print(f"[Heartopia Auto] UI = {_UI}")
    run_gui(config)


if __name__ == "__main__":
    main()
