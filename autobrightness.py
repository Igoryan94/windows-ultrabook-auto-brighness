import cv2
import numpy as np
import win32api
import win32con
import win32gui
import time
import psutil
import json
import os
import subprocess
import threading
import logging
import tkinter as tk

def debug(text):
    logging.info(text)
    print(text)

# Функция для вычисления уровня яркости изображения
def calculate_brightness(image):
    # Конвертируем изображение в формат HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Разделяем каналы HSV
    h, s, v = cv2.split(hsv)
    # Возвращаем среднее значение канала V (яркость)
    return round(np.mean(v))

# Функция для установки яркости дисплея
def set_display_brightness(brightness):
    # Вызываем PowerShell для изменения яркости
    command = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})"
    info = subprocess.STARTUPINFO()
    info.dwFlags = subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", command], startupinfo=info)

# Функция для определения источника питания (батарея или адаптер)
def is_on_battery():
    # Возвращаем состояние питания (True, если питание от адаптера, False, если от батареи)
    battery = psutil.sensors_battery()
    if battery is None:
        return False
    return not battery.power_plugged

def show_in_tray(to_show):
    global nid
    if to_show:
        hWnd = win32gui.CreateWindow("STATIC", "", win32con.WS_OVERLAPPED | win32con.WS_SYSMENU, 0, 0, 0, 0, 0, 0, None, None)
        icon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, 0, 0, win32con.LR_DEFAULTSIZE | win32con.LR_SHARED)
        nid = (hWnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, win32con.WM_USER + 20, icon, "autobrightness")
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
    else:
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        except Exception as e:
            pass

def save_config(event=None):
    with open('config.json', 'w') as f:
        json.dump({'interval_ac': int(entry_interval_ac.get()), 'interval_batt': int(entry_interval_batt.get()), 'adjust_multiplier': float(entry_adjust_multiplier.get())}, f)

# Глобальные переменные
previous_brightness = None
interval_ac = 12
interval_batt = 60
adjust_multiplier = 1.5
running = False

nid = 0

# Настройка логирования
logging.basicConfig(filename='autobrightness.log', level=logging.INFO)

# Создаем файл конфигурации, если он не существует
if not os.path.exists('config.json'):
    with open('config.json', 'w') as f:
        json.dump({'interval_ac': 12, 'interval_batt': 60, 'adjust_multiplier': 1.5}, f)

# Читаем параметры из файла конфигурации
with open('config.json', 'r') as f:
    config = json.load(f)
interval_ac = config['interval_ac']
interval_batt = config['interval_batt']
adjust_multiplier = config['adjust_multiplier']

# Создаем интерфейс
root = tk.Tk()
root.title("Auto Brightness")
root.geometry("300x250")

label_power_source = tk.Label(root, text="Источник питания:")
label_power_source.pack()

label_brightness = tk.Label(root, text="Яркость дисплея:")
label_brightness.pack()

label_status = tk.Label(root, text="Статус:")
label_status.pack(pady=(0, 10))

# Добавляем поля для изменения параметров переменных
label_interval_ac = tk.Label(root, text="Таймаут при питании от сети (сек):")
label_interval_ac.pack()
entry_interval_ac = tk.Entry(root, width=10)
entry_interval_ac.insert(0, str(interval_ac))
entry_interval_ac.pack()
entry_interval_ac.bind('<KeyRelease>', save_config)

label_interval_batt = tk.Label(root, text="Таймаут при питании от батареи (сек):")
label_interval_batt.pack()
entry_interval_batt = tk.Entry(root, width=10)
entry_interval_batt.insert(0, str(interval_batt))
entry_interval_batt.pack()
entry_interval_batt.bind('<KeyRelease>', save_config)

label_adjust_multiplier = tk.Label(root, text="Коэффициент коррекции яркости:")
label_adjust_multiplier.pack()
entry_adjust_multiplier = tk.Entry(root, width=10)
entry_adjust_multiplier.insert(0, str(adjust_multiplier))
entry_adjust_multiplier.pack()
entry_adjust_multiplier.bind('<KeyRelease>', save_config)

def update_labels():
    on_battery = is_on_battery()
    power_source_text = "Сеть" if not on_battery else "Батарея"
    label_power_source.config(text=f"Источник питания: {power_source_text}")

    if previous_brightness is not None:
        brightness_percentage = previous_brightness
    else:
        brightness_percentage = 90

    if brightness_percentage is not None:
        label_brightness.config(text=f"Яркость дисплея: {brightness_percentage}%")

    status_text = "Работает" if running else "Остановлен"
    label_status.config(text=f"Статус: {status_text}")

    root.after(1000, update_labels)

update_labels()

def on_closing():
    global running
    running = False
    show_in_tray(False)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

def main_loop():
    global previous_brightness, interval_ac, interval_batt, adjust_multiplier
    while running:
        # Определить источник питания
        on_battery = is_on_battery()
        # Таймаут на основе режима питания
        interval = int(entry_interval_ac.get()) if not on_battery else int(entry_interval_batt.get())
        adjust_multiplier = float(entry_adjust_multiplier.get())
        debug(f"{'Сеть' if not on_battery else 'Батарея'}, таймаут: {interval} сек")

        # Сделать два замера с некоторым промежутком
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        # Вычисляем уровень яркости
        brightness = calculate_brightness(frame)
        brightness_percentage = int((brightness / 255) * 100)

        # Выравнивание, из-за нелинейной шкалы яркости в Windows 10
        brightness_percentage = min(100, int(brightness_percentage * adjust_multiplier))

        # Берём среднее от текущего и прошлого замера, для более плавного изменения
        if previous_brightness is not None:
            brightness_percentage = int((brightness_percentage + previous_brightness) / 2)

        prev_brightness_debug_text = f" (старая {previous_brightness}%)" if previous_brightness is not None else ""
        debug(f"Яркость изображения: {brightness}, вычисленная яркость дисплея: {brightness_percentage}%{prev_brightness_debug_text}")

        previous_brightness = brightness_percentage

        # Установить яркость дисплея, не ниже 5%
        set_display_brightness(max(5, brightness_percentage))

        # Ждать интервал времени
        time.sleep(interval)

def start_stop():
    global running
    if not running:
        running = True
        threading.Thread(target=main_loop).start()
        button_start_stop.config(text="Стоп")
        update_labels()
        show_in_tray(True)
    else:
        running = False
        button_start_stop.config(text="Старт")
        update_labels()
        show_in_tray(False)

# Кнопка "Старт/стоп"
button_start_stop = tk.Button(root, text="Старт", command=start_stop)
button_start_stop.pack(pady=15)

root.mainloop()