@echo off
REM เปิด Heartopia Auto แบบ Administrator (แก้ปัญหา Windows บล็อกการสั่งเมาส์)
cd /d "%~dp0"
powershell -Command "Start-Process -FilePath '%~dp0.venv\Scripts\python.exe' -ArgumentList 'run.py' -WorkingDirectory '%~dp0' -Verb RunAs"
