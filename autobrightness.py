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

# Глобальные переменные
previous_brightness = None

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
    battery = psutil.sensors_battery()
    if battery is None:
        return False
    return not battery.power_plugged

def debug(text):
    logging.info(text)
    print(text)

# Создаем иконку в системном трее
hWnd = win32gui.CreateWindow("STATIC", "", win32con.WS_OVERLAPPED | win32con.WS_SYSMENU, 0, 0, 0, 0, 0, 0, 0, None)
icon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, 0, 0, win32con.LR_DEFAULTSIZE | win32con.LR_SHARED)
nid = (hWnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, win32con.WM_USER + 20, icon, "autobrightness")
win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

# Основной цикл
while True:
    # Определить источник питания
    on_battery = is_on_battery()
    interval = 30 if not on_battery else 90  # Таймаут на основе режима питания
    debug(f"{"Сеть" if not on_battery else "Батарея"}, таймаут: {interval} сек")

    # Сделать два замера с некоторым промежутком
    cap = cv2.VideoCapture(0)
    ret, frame1 = cap.read()
    time.sleep(0.3)
    ret, frame2 = cap.read()
    cap.release()

    # Вычислить уровень яркости для каждого замера
    brightness1 = calculate_brightness(frame1)
    brightness2 = calculate_brightness(frame2)

    # Вычислить среднее значение яркости
    brightness = round((brightness1 + brightness2) / 2)
    brightness_percentage = int((brightness / 255) * 100)

    # Выравнивание, из-за нелинейной шкалы яркости в Windows 10
    brightness_percentage = min(100, int(brightness_percentage * 1.53))

    # Берём среднее от текущего и прошлого замера, для более плавного изменения
    if previous_brightness is not None:
        brightness_percentage = int((brightness_percentage + previous_brightness) / 2)

    prev_brightness_debug_text = f" (старая {previous_brightness}%)" if previous_brightness is not None else ""
    debug(f"Яркость изображения: {brightness}, вычисленная яркость дисплея: {brightness_percentage}%{prev_brightness_debug_text}")

    previous_brightness = brightness_percentage

    # Установить яркость дисплея
    set_display_brightness(brightness_percentage)

    # Ждать интервал времени
    time.sleep(interval)