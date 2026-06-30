"""
ระบบมองเห็น (computer vision): หา template (รูปปุ่ม/UI) ในภาพหน้าจอด้วย OpenCV

template คือไฟล์ .png เล็กๆ ที่ตัด crop มาจากหน้าจอเกม เก็บไว้ใน assets/templates/
ใช้เครื่องมือ tools/capture.py เพื่อตัด crop ได้สะดวก
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from .i18n import t


@dataclass
class Match:
    found: bool
    score: float
    center: tuple[int, int]          # จุดกึ่งกลางที่เจอ (พิกัดในภาพ)
    rect: tuple[int, int, int, int]  # (x, y, w, h)
    name: str = ""

    def __bool__(self) -> bool:
        return self.found


_NOT_FOUND = lambda name="": Match(False, 0.0, (0, 0), (0, 0, 0, 0), name)


class Vision:
    def __init__(self, templates_dir: str, config: dict):
        self.templates_dir = templates_dir
        v = config.get("vision", {})
        self.threshold = float(v.get("match_threshold", 0.80))
        self.scales = list(v.get("scales", [1.0]))
        self.grayscale = bool(v.get("grayscale", False))
        self._cache: dict[str, np.ndarray | None] = {}
        self._warned: set[str] = set()

    # --- การโหลด template ---
    def _template_path(self, name: str) -> str:
        if not name.lower().endswith(".png"):
            name = name + ".png"
        return os.path.join(self.templates_dir, name)

    def load(self, name: str) -> np.ndarray | None:
        if name in self._cache:
            return self._cache[name]
        path = self._template_path(name)
        img = cv2.imread(path, cv2.IMREAD_COLOR) if os.path.exists(path) else None
        self._cache[name] = img
        return img

    def has_template(self, name: str) -> bool:
        return os.path.exists(self._template_path(name))

    # --- การค้นหา ---
    def find(self, frame: np.ndarray, name: str, threshold: float | None = None) -> Match:
        template = self.load(name)
        if template is None:
            if name not in self._warned:
                self._warned.add(name)
                print(t("vision.missing", name=name))
            return _NOT_FOUND(name)
        return self.match(frame, template, threshold if threshold is not None else self.threshold, name)

    def match(self, frame: np.ndarray, template: np.ndarray,
              threshold: float, name: str = "") -> Match:
        f, t = frame, template
        if self.grayscale:
            f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            t = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        best = None  # (score, loc, (w,h))
        for s in self.scales:
            ts = t if s == 1.0 else cv2.resize(t, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if ts.shape[0] > f.shape[0] or ts.shape[1] > f.shape[1]:
                continue
            res = cv2.matchTemplate(f, ts, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if best is None or max_val > best[0]:
                h, w = ts.shape[:2]
                best = (max_val, max_loc, (w, h))

        if best is None:
            return _NOT_FOUND(name)

        score, loc, (w, h) = best
        cx, cy = loc[0] + w // 2, loc[1] + h // 2
        return Match(score >= threshold, float(score), (cx, cy), (loc[0], loc[1], w, h), name)

    def find_all(self, frame: np.ndarray, name: str, threshold: float | None = None,
                 dedup_distance: int = 30) -> list[Match]:
        """หา 'ทุกตำแหน่ง' ที่ match (เช่นหลายเตา) คืน list ของ Match (กรองตำแหน่งซ้ำที่ใกล้กัน)"""
        template = self.load(name)
        if template is None:
            if name not in self._warned:
                self._warned.add(name)
                print(t("vision.missing", name=name))
            return []
        return self.match_all(frame, template,
                              threshold if threshold is not None else self.threshold,
                              name, dedup_distance)

    def match_all(self, frame: np.ndarray, template: np.ndarray, threshold: float,
                  name: str = "", dedup_distance: int = 30) -> list[Match]:
        f, tpl = frame, template
        if self.grayscale:
            f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            tpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if tpl.shape[0] > f.shape[0] or tpl.shape[1] > f.shape[1]:
            return []
        res = cv2.matchTemplate(f, tpl, cv2.TM_CCOEFF_NORMED)
        h, w = tpl.shape[:2]
        ys, xs = np.where(res >= threshold)
        if len(xs) == 0:
            return []
        scores = res[ys, xs]
        order = np.argsort(-scores)  # คะแนนสูงก่อน
        picked: list[tuple[int, int]] = []
        out: list[Match] = []
        for i in order:
            x, y, s = int(xs[i]), int(ys[i]), float(scores[i])
            cx, cy = x + w // 2, y + h // 2
            if any(abs(cx - px) < dedup_distance and abs(cy - py) < dedup_distance
                   for px, py in picked):
                continue
            picked.append((cx, cy))
            out.append(Match(True, s, (cx, cy), (x, y, w, h), name))
        return out

    def find_all_known(self, frame: np.ndarray) -> list[Match]:
        """ลองหา template ทุกไฟล์ในโฟลเดอร์ -> ใช้สำหรับโหมดทดสอบการตรวจจับ"""
        results = []
        if not os.path.isdir(self.templates_dir):
            return results
        for fn in sorted(os.listdir(self.templates_dir)):
            if fn.lower().endswith(".png"):
                results.append(self.find(frame, fn[:-4]))
        return results
