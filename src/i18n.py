"""
ระบบ 2 ภาษา (i18n) — English / ไทย

วิธีใช้:
    from .i18n import t, set_language
    set_language("en")          # หรือ "th"
    t("btn.start")              # คืนข้อความตามภาษาปัจจุบัน
    t("cook.round", n=3)        # รองรับ placeholder แบบ {n}

ถ้าไม่เจอ key ในภาษาปัจจุบัน จะ fallback เป็น English แล้วเป็นตัว key เอง
"""
from __future__ import annotations

_LANG = "en"

LANGUAGES = [("English", "en"), ("ไทย", "th")]


def set_language(lang: str) -> None:
    global _LANG
    if lang in _TR:
        _LANG = lang


def get_language() -> str:
    return _LANG


def t(tkey: str, **kwargs) -> str:
    table = _TR.get(_LANG, _TR["en"])
    s = table.get(tkey)
    if s is None:
        s = _TR["en"].get(tkey, tkey)
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s


_TR: dict[str, dict[str, str]] = {
    "en": {
        # --- GUI ---
        "win.title": "Heartopia Auto",
        "frame.window": "1) Game window",
        "btn.refresh": "Refresh",
        "frame.task": "2) Task & settings",
        "lbl.repeat": "Stop after N dishes (0 = until stopped):",
        "lbl.scan_delay": "Scan delay (s):",
        "chk.auto_latest": "Auto-select latest menu (repeat same dish)",
        "chk.background": "Background mode — switch away while running (do NOT minimize the window)",
        "btn.start": "▶ Start",
        "btn.stop": "■ Stop",
        "btn.detect": "🔍 Detect test",
        "lbl.lang": "Language:",
        "status.ready": "● Ready",
        "status.running": "● Running",
        "frame.log": "Log",
        "lbl.emergency": "Emergency stop: press F9, or shove the mouse into the top-left corner of the screen",
        "nav.control": "Control",
        "nav.settings": "Settings",
        "app.subtitle": "Image-recognition automation for Heartopia",
        "switch.on": "On",
        "switch.off": "Off",
        "settings.appearance": "Appearance",
        "settings.theme": "Theme",
        "theme.auto": "Follow system",
        "theme.dark": "Dark",
        "theme.light": "Light",
        "settings.about": "About & safety",
        "settings.about_body": "Heartopia Auto works by reading the screen and clicking — it never modifies game files.\n\n"
                               "⚠ Using automation may violate the game's Terms of Service and risks an account ban. "
                               "Use at your own risk and consider testing on a secondary account.",
        "info.started": "Started",
        "info.stopped": "Stopped",
        # --- GUI runtime logs ---
        "log.admin_yes": "Running as Administrator ✓",
        "log.admin_no": "⚠ Not running as Administrator — if Start shows 'Windows blocked mouse input', "
                        "relaunch with run_as_admin.bat (the game runs as Admin)",
        "log.autodetect": "Auto-detected game window: {title}",
        "log.select_window_first": "✋ Please select the game window first (click Refresh)",
        "log.select_window_short": "✋ Select the game window first",
        "log.invalid_number": "⚠ Repeat / heat values must be numbers — keeping previous values",
        "log.start_task": "=== Start task: {task} ===",
        "log.stopped_user": "■ Stopped by user",
        "log.emergency_stop": "■ Emergency stop: {msg}",
        "log.input_blocked": "⛔ {msg}",
        "log.window_not_found": "✋ {msg}",
        "log.error": "✗ Error: {msg}",
        "log.stopping": "… Stopping",
        "log.busy_detect": "Busy running — stop first, then run detect",
        "log.detect_header": "--- Detect test ---",
        "log.captured": "Captured {w}x{h} px (mean pixel {mean})",
        "log.black_warn": "⚠ Image is all black! → don't minimize the game window / some engines can't be "
                          "captured via PrintWindow — if you're in background mode, turn it off",
        "log.no_templates": "No template files in assets/templates/ yet — capture them with tools/capture.py first",
        "tag.found": "✓ found ",
        "tag.notfound": "✗ none  ",
        "log.detect_row": "  {tag} {name}  score={score}",
        "log.saved_detect": "Saved detection image: {path}",
        "log.detect_failed": "✗ Detect failed: {msg}",
        # --- Task names ---
        "task.cooking.name": "Cooking",
        "task.cooking.desc": "Multi-stove auto-tap: clicks cook / heat / collect / cook-again wherever it sees them",
        # --- Cooking logs ---
        "cook.start": "▶ Auto-cook started (multi-stove). Watching: {tpls}{bg}",
        "cook.no_templates_short": "✋ No cooking templates captured. Capture at least one of: "
                                   "cook_start / heat_adjust / cook_done / cook_again",
        "cook.tapped": "  Tapped → {summary}",
        "cook.idle": "  (scanning… best scores: {scores}) — if all < threshold, recapture templates or lower vision.match_threshold",
        "cook.interact": "  ⏎ Pressed [{key}] to open the stove menu / continue",
        "cook.mode.latest": "auto-select latest menu",
        "cook.mode.recipe": "recipe '{recipe}'",
        "cook.bg_suffix": " | background mode",
        "cook.round": "── Round {n} ──",
        "cook.cant_start": "  ⚠ Can't start cooking (no 'cook_again'/'cook_start' found) (fail streak {a}/{b})",
        "cook.cant_collect": "  ⚠ Can't collect food (no 'cook_done' found) (fail streak {a}/{b})",
        "cook.fail_stop": "✋ Failed {n} rounds in a row — maybe out of ingredients/energy or the UI changed, stopping",
        "cook.done": "■ Auto-cook stopped — collected {n} dishes",
        "cook.sel_latest": "  Selected latest menu",
        "cook.sel_recipe": "  Selected recipe '{recipe}'",
        "cook.no_start_tpl": "  ⚠ 'cook_start' (and 'cook_again') not captured yet",
        "cook.again": "  ▷ Cook again (cook_again)",
        "cook.startbtn": "  ▷ Start cooking (cook_start)",
        "cook.collected": "  ✓ Collected food (cook_done)",
        "cook.no_collect_tpl": "  (cook_done not set — skipping collect step)",
        "cook.heat_wait": "  Heat: waiting to press 'heat_adjust' up to {n}x",
        "cook.heat_n": "    Heat adjust #{n}",
        "cook.heat_partial": "    (adjusted {a}/{b} times within the time window)",
        # --- Bot ---
        "bot.bg_child": "  (background) sending clicks to child window hwnd={hwnd}",
        # --- Vision ---
        "vision.missing": "[vision] ⚠ template '{name}.png' not found in assets/templates/ "
                          "(skipping — capture it with tools/capture.py)",
        # --- Exceptions ---
        "err.window_gone": "Game window is gone or closed",
        "err.window_zero": "Game window size is 0 (maybe minimized) — restore the window",
        "err.failsafe": "Mouse moved to top-left corner — emergency stop",
        "err.input_blocked_mouse": "Windows blocked mouse input — usually because the game runs as Administrator.\n"
                                   "Fix: close the bot and reopen it via right-click → Run as administrator "
                                   "(or double-click run_as_admin.bat)",
        "err.input_blocked_key": "Windows blocked keyboard input — try running the bot via Run as administrator",
        "err.stopped_user": "User requested stop",
    },
    "th": {
        # --- GUI ---
        "win.title": "Heartopia Auto",
        "frame.window": "1) หน้าต่างเกม",
        "btn.refresh": "รีเฟรช",
        "frame.task": "2) งานและการตั้งค่า",
        "lbl.repeat": "หยุดเมื่อได้ N จาน (0 = จนกดหยุด):",
        "lbl.scan_delay": "หน่วงสแกน (วิ):",
        "chk.auto_latest": "เลือกเมนูล่าสุดอัตโนมัติ (ทำเมนูเดิมซ้ำ)",
        "chk.background": "โหมดเบื้องหลัง — พับจอ/สลับไปทำอย่างอื่นได้ (อย่าย่อหน้าต่าง)",
        "btn.start": "▶ เริ่ม",
        "btn.stop": "■ หยุด",
        "btn.detect": "🔍 ทดสอบการตรวจจับ",
        "lbl.lang": "ภาษา:",
        "status.ready": "● พร้อม",
        "status.running": "● กำลังทำงาน",
        "frame.log": "Log",
        "lbl.emergency": "หยุดฉุกเฉิน: กด F9 หรือ เลื่อนเมาส์ชนมุมซ้ายบนสุดของจอ",
        "nav.control": "ควบคุม",
        "nav.settings": "ตั้งค่า",
        "app.subtitle": "บอทเล่น Heartopia ด้วยการอ่านภาพหน้าจอ",
        "switch.on": "เปิด",
        "switch.off": "ปิด",
        "settings.appearance": "การแสดงผล",
        "settings.theme": "ธีม",
        "theme.auto": "ตามระบบ",
        "theme.dark": "มืด",
        "theme.light": "สว่าง",
        "settings.about": "เกี่ยวกับ & ความปลอดภัย",
        "settings.about_body": "Heartopia Auto ทำงานด้วยการอ่านภาพหน้าจอแล้วคลิก — ไม่ยุ่งกับไฟล์เกม\n\n"
                               "⚠ การใช้บอทอาจผิดเงื่อนไขการใช้งาน (ToS) ของเกม และเสี่ยงโดนแบนบัญชี "
                               "ใช้ด้วยความรับผิดชอบของตัวเอง แนะนำให้ทดสอบกับบัญชีรอง",
        "info.started": "เริ่มทำงานแล้ว",
        "info.stopped": "หยุดแล้ว",
        # --- GUI runtime logs ---
        "log.admin_yes": "รันแบบ Administrator ✓",
        "log.admin_no": "⚠ ไม่ได้รันแบบ Admin — ถ้ากด Start แล้วเจอ 'Windows บล็อกการสั่งเมาส์' "
                        "ให้เปิดใหม่ด้วย run_as_admin.bat (เพราะตัวเกมรันแบบ Admin)",
        "log.autodetect": "พบหน้าต่างเกมอัตโนมัติ: {title}",
        "log.select_window_first": "✋ กรุณาเลือกหน้าต่างเกมก่อน (กดรีเฟรช)",
        "log.select_window_short": "✋ เลือกหน้าต่างเกมก่อน",
        "log.invalid_number": "⚠ ค่าจำนวนรอบ/ปรับไฟต้องเป็นตัวเลข — ใช้ค่าเดิม",
        "log.start_task": "=== เริ่มงาน: {task} ===",
        "log.stopped_user": "■ หยุดโดยผู้ใช้",
        "log.emergency_stop": "■ หยุดฉุกเฉิน: {msg}",
        "log.input_blocked": "⛔ {msg}",
        "log.window_not_found": "✋ {msg}",
        "log.error": "✗ เกิดข้อผิดพลาด: {msg}",
        "log.stopping": "… กำลังสั่งหยุด",
        "log.busy_detect": "กำลังทำงานอยู่ — หยุดก่อนจึงทดสอบได้",
        "log.detect_header": "--- ทดสอบการตรวจจับ template ---",
        "log.captured": "จับภาพได้ {w}x{h} px (ค่าเฉลี่ยสี {mean})",
        "log.black_warn": "⚠ ภาพเป็นจอดำ! → อย่าย่อหน้าต่างเกม / บาง engine จับด้วย PrintWindow ไม่ได้ "
                          "— ถ้าเป็นโหมดเบื้องหลังให้ลองปิดโหมดนี้",
        "log.no_templates": "ยังไม่มีไฟล์ template ใน assets/templates/ — capture ด้วย tools/capture.py ก่อน",
        "tag.found": "✓ เจอ  ",
        "tag.notfound": "✗ ไม่เจอ",
        "log.detect_row": "  {tag} {name}  score={score}",
        "log.saved_detect": "บันทึกภาพผลตรวจจับ: {path}",
        "log.detect_failed": "✗ ทดสอบล้มเหลว: {msg}",
        # --- Task names ---
        "task.cooking.name": "ทำอาหาร (Cooking)",
        "task.cooking.desc": "แตะทุกอย่างที่เห็น รองรับหลายเตา: คลิก ปรุง/ปรับไฟ/เก็บ/ทำต่อ ทุกจุดที่เจอ",
        # --- Cooking logs ---
        "cook.start": "▶ เริ่ม auto ทำอาหาร (หลายเตา) กำลังจับ: {tpls}{bg}",
        "cook.no_templates_short": "✋ ยังไม่มี template ทำอาหาร — capture อย่างน้อย 1 อย่าง: "
                                   "cook_start / heat_adjust / cook_done / cook_again",
        "cook.tapped": "  คลิก → {summary}",
        "cook.idle": "  (กำลังสแกน… ค่าสูงสุด: {scores}) — ถ้าทุกตัว < เกณฑ์ ให้ capture ใหม่ หรือลด vision.match_threshold",
        "cook.interact": "  ⏎ กดปุ่ม [{key}] เพื่อเปิดเมนูเตา / ดำเนินการต่อ",
        "cook.mode.latest": "เลือกเมนูล่าสุดอัตโนมัติ",
        "cook.mode.recipe": "เมนูตามสูตร '{recipe}'",
        "cook.bg_suffix": " | โหมดเบื้องหลัง",
        "cook.round": "── รอบที่ {n} ──",
        "cook.cant_start": "  ⚠ เริ่มปรุงไม่ได้ (ไม่เจอ 'cook_again'/'cook_start') (ไม่สำเร็จติดต่อกัน {a}/{b})",
        "cook.cant_collect": "  ⚠ เก็บอาหารไม่ได้ (ไม่เจอ 'cook_done') (ไม่สำเร็จติดต่อกัน {a}/{b})",
        "cook.fail_stop": "✋ ทำไม่สำเร็จติดต่อกัน {n} รอบ — อาจวัตถุดิบ/พลังงานหมด หรือหน้าจอเปลี่ยน จึงหยุด",
        "cook.done": "■ หยุด auto ทำอาหาร — เก็บอาหารได้ {n} จาน",
        "cook.sel_latest": "  เลือกเมนูล่าสุด",
        "cook.sel_recipe": "  เลือกสูตร '{recipe}'",
        "cook.no_start_tpl": "  ⚠ ยังไม่ได้ capture 'cook_start' (และ 'cook_again')",
        "cook.again": "  ▷ ทำอาหารต่อ (cook_again)",
        "cook.startbtn": "  ▷ เริ่มปรุง (cook_start)",
        "cook.collected": "  ✓ เก็บอาหาร (cook_done)",
        "cook.no_collect_tpl": "  (ไม่ได้ตั้ง cook_done — ข้ามขั้นเก็บอาหาร)",
        "cook.heat_wait": "  ปรับไฟ: รอกดปุ่ม 'heat_adjust' สูงสุด {n} ครั้ง",
        "cook.heat_n": "    ปรับไฟครั้งที่ {n}",
        "cook.heat_partial": "    (ปรับไฟได้ {a}/{b} ครั้งในเวลาที่กำหนด)",
        # --- Bot ---
        "bot.bg_child": "  (โหมดเบื้องหลัง) ส่งคลิกไปยัง child window hwnd={hwnd}",
        # --- Vision ---
        "vision.missing": "[vision] ⚠ ไม่พบไฟล์ template '{name}.png' ใน assets/templates/ "
                          "(ข้ามไปก่อน — capture รูปนี้ด้วย tools/capture.py)",
        # --- Exceptions ---
        "err.window_gone": "หน้าต่างเกมหายไปหรือถูกปิด",
        "err.window_zero": "ขนาดหน้าต่างเกมเป็น 0 (อาจถูกย่ออยู่) — ลองคืนขนาดหน้าต่าง",
        "err.failsafe": "เลื่อนเมาส์ชนมุมซ้ายบน — หยุดฉุกเฉิน",
        "err.input_blocked_mouse": "Windows บล็อกการสั่งเมาส์ — ส่วนใหญ่เพราะตัวเกมรันแบบ Administrator\n"
                                   "วิธีแก้: ปิดบอทแล้วเปิดใหม่ด้วยคลิกขวา → Run as administrator "
                                   "(หรือดับเบิลคลิก run_as_admin.bat)",
        "err.input_blocked_key": "Windows บล็อกการสั่งคีย์บอร์ด — ลองรันบอทแบบ Run as administrator",
        "err.stopped_user": "ผู้ใช้สั่งหยุด",
    },
}
