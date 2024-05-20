@echo off
@pip install pyinstaller

rem Очистка
rmdir /s /q dist
rmdir /s /q build

rem Билд
pyinstaller --onefile -F -w autobrightness.py

pause