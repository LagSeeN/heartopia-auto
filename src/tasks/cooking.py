"""
งานทำอาหารอัตโนมัติ (Cooking) — โหมด "แตะทุกอย่างที่เห็น" รองรับหลายเตา

หลักการ (เลียนแบบบอท auto-tap ที่ใช้งานได้ดี):
  ทุกๆ รอบสแกน จะหา "ทุกตำแหน่ง" ของ template ที่ตั้งไว้ (cook_again / cook_start /
  heat_adjust / cook_done) แล้ว "คลิกหมดทุกจุดที่เจอ" → ทำให้:
    - ทำได้ "หลายเตาพร้อมกัน" (เพราะหาทุกตำแหน่ง ไม่ใช่จุดเดียว)
    - ไม่ต้องนับ/จับเวลา heat adjust เอง — เห็นปุ่มปรับไฟก็คลิก, เห็นปุ่มเก็บก็เก็บ,
      เห็นปุ่มทำต่อก็ทำต่อ ระบบจัดการเองตามที่เห็นบนจอ

กันคลิกรัวจุดเดิม: มี cooldown ต่อตำแหน่ง (click_cooldown)
หยุด: กด Stop / F9 / เมาส์ชนมุมจอ  หรือ ตั้ง repeat > 0 (หยุดเมื่อเก็บอาหารครบ N จาน)

template ที่ใช้ (เท่าที่ capture ไว้): cook_start, heat_adjust, cook_done, cook_again
"""
from __future__ import annotations

import time

from ..bot import Bot
from ..i18n import t
from ..task import BaseTask

# ลำดับ flow: คลิกตัวเตาเปิดเมนู -> ปุ่มปรุง -> ปรับไฟ -> เก็บอาหาร -> (เมนูปิด) -> คลิกเตาใหม่
DEFAULT_CLICK_TEMPLATES = ["stove", "cook_start", "heat_adjust", "cook_done", "cook_again"]


class CookingTask(BaseTask):
    name_key = "task.cooking.name"
    desc_key = "task.cooking.desc"

    def run(self, bot: Bot) -> None:
        cfg = self.config.get("cooking", {})
        repeat = int(cfg.get("repeat", 0))
        scan_delay = float(cfg.get("scan_delay", 0.3))
        dedup = int(cfg.get("dedup_distance", 40))
        cooldown = float(cfg.get("click_cooldown", 0.8))
        click_delay = float(cfg.get("multi_click_delay", 0.05))
        threshold = cfg.get("match_threshold", None)  # None = ใช้ค่า vision.match_threshold
        interact_key = (cfg.get("interact_key") or "").strip()
        interact_idle = max(1, int(cfg.get("interact_idle_scans", 5)))
        names = list(cfg.get("click_templates", DEFAULT_CLICK_TEMPLATES))

        bot.focus()
        active = [n for n in names if bot.vision.has_template(n)]
        if not active:
            bot.log(t("cook.no_templates_short"))
            return
        bg = t("cook.bg_suffix") if bot.background else ""
        bot.log(t("cook.start", tpls=", ".join(active), bg=bg))

        collected = 0
        idle = 0
        recent: list[tuple[int, int, float]] = []  # ตำแหน่งที่เพิ่งคลิก (กัน cooldown)
        while repeat == 0 or collected < repeat:
            bot.check_stop()
            frame = bot.screenshot()
            now = time.time()
            recent = [(x, y, ts) for (x, y, ts) in recent if now - ts < cooldown]

            tally: dict[str, int] = {}
            clicked_here: list[tuple[int, int]] = []
            for name in active:
                for m in bot.vision.find_all(frame, name, threshold=threshold, dedup_distance=dedup):
                    cx, cy = m.center
                    # กันคลิกซ้ำในรอบสแกนเดียวกัน (template คนละตัวแต่จุดเดียวกัน)
                    if any(abs(cx - px) < dedup and abs(cy - py) < dedup for px, py in clicked_here):
                        continue
                    # กันคลิกซ้ำจุดเดิมเร็วเกินไป (ข้ามรอบสแกน)
                    if cooldown > 0 and any(abs(cx - px) < dedup and abs(cy - py) < dedup
                                            for px, py, _ in recent):
                        continue
                    bot.tap_point((cx, cy))            # คลิกเร็ว ไม่หน่วง
                    clicked_here.append((cx, cy))
                    recent.append((cx, cy, time.time()))
                    tally[name] = tally.get(name, 0) + 1
                    if name == "cook_done":
                        collected += 1
                    if click_delay > 0:
                        bot.sleep(click_delay)         # หน่วงสั้นๆ ระหว่างคลิกแต่ละจุด

            if tally:
                idle = 0
                summary = ", ".join(f"{k}×{v}" for k, v in tally.items())
                bot.log(t("cook.tapped", summary=summary))
            else:
                # ไม่ได้คลิกอะไรเลย
                idle += 1
                # กดปุ่ม interact (เช่น ENTER) เพื่อเปิดเมนูเตา/แตะดำเนินการต่อ
                if interact_key and idle % interact_idle == 0:
                    bot.press_key(interact_key)
                    bot.log(t("cook.interact", key=interact_key.upper()))
                # log ค่าคะแนนสูงสุดของแต่ละปุ่มเป็นระยะ เพื่อ debug ว่าทำไมไม่คลิก
                if idle == 2 or idle % 15 == 0:
                    scores = ", ".join(f"{n}:{bot.vision.find(frame, n, threshold=threshold).score:.2f}"
                                       for n in active)
                    bot.log(t("cook.idle", scores=scores))
            bot.sleep(scan_delay)

        bot.log(t("cook.done", n=collected))
