"""ทะเบียน task ทั้งหมด — เพิ่ม task ใหม่ที่นี่"""
from __future__ import annotations

from ..task import BaseTask
from .cooking import CookingTask


def get_all_tasks(config: dict) -> list[BaseTask]:
    """คืน instance ของทุก task ที่พร้อมใช้งาน (เรียงตามลำดับที่จะแสดงใน GUI)"""
    return [
        CookingTask(config),
        # เพิ่มงานใหม่ที่นี่ เช่น FishingTask(config), GardeningTask(config), ...
    ]
