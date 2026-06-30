"""ข้อยกเว้น (exceptions) ที่ใช้ควบคุมการหยุดทำงานของบอท"""


class BotStopped(Exception):
    """ผู้ใช้สั่งหยุด (กดปุ่ม Stop หรือ F9)"""


class FailsafeTriggered(Exception):
    """หยุดฉุกเฉิน - ตรวจพบเมาส์ถูกเลื่อนไปชนมุมซ้ายบนของจอ"""


class WindowNotFound(Exception):
    """หาหน้าต่างเกมไม่เจอ"""


class InputBlocked(Exception):
    """Windows บล็อกการสั่งเมาส์/คีย์บอร์ด — ส่วนใหญ่เพราะเกมรันแบบ Administrator
    แต่บอทไม่ได้รัน ให้เปิดบอทด้วย 'Run as administrator' (หรือ run_as_admin.bat)"""
