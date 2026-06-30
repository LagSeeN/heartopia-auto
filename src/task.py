"""
โครงสร้าง task: คลาสฐาน BaseTask + ตัวจัดการรายการ task

วิธีเพิ่มงานใหม่ (เช่น ตกปลา / ทำสวน):
1. สร้างไฟล์ใน src/tasks/ สืบทอด BaseTask
2. กำหนด name, description, และเขียนเมธอด run(self, bot)
3. ลงทะเบียนใน src/tasks/__init__.py (ฟังก์ชัน get_all_tasks)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .bot import Bot


class BaseTask(ABC):
    #: คีย์ i18n สำหรับชื่อที่แสดงใน GUI
    name_key: str = "task.unknown.name"
    #: คีย์ i18n สำหรับคำอธิบายสั้นๆ
    desc_key: str = "task.unknown.desc"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def run(self, bot: Bot) -> None:
        """ลอจิกหลักของงาน — เรียกใช้ bot.find / bot.click / bot.wait_for ฯลฯ
        ควรเรียก bot.check_stop() เป็นระยะ (helper ส่วนใหญ่เช็กให้อยู่แล้ว)"""
        raise NotImplementedError
