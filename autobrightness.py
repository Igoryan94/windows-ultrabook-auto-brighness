# pip install opencv-python numpy psutil

import cv2
import numpy as np
import ctypes
import time
import psutil

# Функция для вычисления уровня яркости изображения
def calculate_brightness(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    return np.mean(v)

# Функция для установки яркости дисплея
def set_display_brightness(brightness):
    ctypes.c_ulong(0)
    ctypes.windll.user32.SetMonitorBrightness(0, int(brightness))

# Функция для определения источника питания (батарея или адаптер)
def get_power_source():
    return psutil.sensors_battery().power_plugged

# Основной цикл
while True:
    # Определить источник питания
    power_source = get_power_source()
    interval = 30 if power_source else 180  # 30 секунд, если питание от адаптера, 3 минуты, если от батареи

    # Сделать снимок с веб-камеры
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    # Вычислить уровень яркости
    brightness = calculate_brightness(frame)
    brightness_percentage = int((brightness / 255) * 100)

    # Установить яркость дисплея
    set_display_brightness(brightness_percentage)

    # Ждать интервал времени
    time.sleep(interval)