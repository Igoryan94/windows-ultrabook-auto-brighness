import cv2
import numpy as np
import win32api
import win32con
import win32gui
import time
import psutil
import subprocess
import logging

# Настройка логирования
logging.basicConfig(filename='autobrightness.log', level=logging.INFO)

# Функция для вычисления уровня яркости изображения
def calculate_brightness(image):
    # Конвертируем изображение в формат HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Разделяем каналы HSV
    h, s, v = cv2.split(hsv)
    # Возвращаем среднее значение канала V (яркость)
    return np.mean(v)

# Функция для установки яркости дисплея
def set_display_brightness(brightness):
    # Вызываем PowerShell для изменения яркости
    command = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})"
    subprocess.run(["powershell", "-Command", command])

# Функция для определения источника питания (батарея или адаптер)
def is_on_battery():
    # Возвращаем состояние питания (True, если питание от адаптера, False, если от батареи)
    return psutil.sensors_battery().power_plugged

# Создаем иконку в системном трее
hWnd = win32gui.CreateWindow("STATIC", "", win32con.WS_OVERLAPPED | win32con.WS_SYSMENU, 0, 0, 0, 0, 0, 0, 0, None)
icon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, 0, 0, win32con.LR_DEFAULTSIZE | win32con.LR_SHARED)
nid = (hWnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, win32con.WM_USER + 20, icon, "autobrightness")
win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

# Основной цикл
while True:
    # Определить источник питания
    interval = 30 if not is_on_battery() else 90  # 30 секунд, если питание от адаптера, 90 секунд, если от батареи

    # Сделать снимок с веб-камеры
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    # Вычислить уровень яркости
    brightness = calculate_brightness(frame)
    brightness_percentage = int((brightness / 255) * 100)

    # Выравнивание, из-за нелинейной шкалы яркости в Windows 10
    brightness_percentage = min(100, int(brightness_percentage * 1.53))

    # Вывод текущего значения яркости
    logging.info(f"Текущая яркость: {brightness_percentage}%")
    print(f"Текущая яркость: {brightness_percentage}%")

    # Установить яркость дисплея
    set_display_brightness(brightness_percentage)

    # Ждать интервал времени
    time.sleep(interval)