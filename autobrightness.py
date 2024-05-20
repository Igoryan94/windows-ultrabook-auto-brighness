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
import tkinter.ttk as ttk
import ttkthemes as ttkthemes

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
        json.dump({'interval_ac': int(entry_interval_ac.get()), 'interval_batt': int(entry_interval_batt.get()), 'brightness_adjust': scale_brightness_adjust.get()}, f)

# Глобальные переменные
default_interval_ac = 12
default_interval_batt = 60
default_brightness_adjust = 50

interval_ac = default_interval_ac
interval_batt = default_interval_batt
brightness_adjust = default_brightness_adjust

brightness_avg_count = 3
previous_brightnesses = []

brightness_offset = 3

running = False

nid = 0

# Настройка логирования
logging.basicConfig(filename='autobrightness.log', level=logging.INFO)

# Загрузка конфигурации из файла
config_file = 'config.json'
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        # Если файл существует, загружаем его содержимое
        config = json.load(f)
else:
    config = {}
    # Если файл не существует, создаем пустой словарь

# Установка значений по умолчанию, если они не существуют
config.setdefault('interval_ac', default_interval_ac)
config.setdefault('interval_batt', default_interval_batt)
config.setdefault('brightness_adjust', default_brightness_adjust)

# Сохранение конфигурации в файл
with open(config_file, 'w') as f:
    # сохраяем конфигурационный файл с обновленными значениями
    json.dump(config, f)

# Теперь можно использовать значения конфигурации
interval_ac = config['interval_ac']
interval_batt = config['interval_batt']
brightness_adjust = config['brightness_adjust']

# Создаем интерфейс
root = tk.Tk()
root.title("UltraBook Auto Brightness")
root.geometry("330x285")

# Применяем тему
ttkthemes.themed_style = ttkthemes.ThemedStyle(root)
ttkthemes.themed_style.set_theme("vista")

# Настраиваем видимые элементы окна
label_power_source = ttk.Label(root, text="Источник питания:")
label_power_source.pack(pady=(20, 0))

label_brightness = ttk.Label(root, text="Яркость дисплея:")
label_brightness.pack()

label_status = ttk.Label(root, text="Статус:")
label_status.pack(pady=(0, 10))

# Добавляем элементы для изменения параметров переменных
label_interval_ac = ttk.Label(root, text="Таймаут при питании от сети (сек):")
label_interval_ac.pack()
entry_interval_ac = ttk.Entry(root, width=10)
entry_interval_ac.insert(0, str(interval_ac))
entry_interval_ac.pack()
entry_interval_ac.bind('<KeyRelease>', save_config)

label_interval_batt = ttk.Label(root, text="Таймаут при питании от батареи (сек):")
label_interval_batt.pack()
entry_interval_batt = ttk.Entry(root, width=10)
entry_interval_batt.insert(0, str(interval_batt))
entry_interval_batt.pack()
entry_interval_batt.bind('<KeyRelease>', save_config)

label_brightness_adjust = ttk.Label(root, text="Регулировка яркости (в процентах):")
label_brightness_adjust.pack(pady=(10, 0))
scale_brightness_adjust = ttk.Scale(root, from_=0, to=100, orient=tk.HORIZONTAL, length=200, command=save_config)
scale_brightness_adjust.set(brightness_adjust)
scale_brightness_adjust.pack()

def update_labels():
    global previous_brightnesses, brightness_avg_count
    on_battery = is_on_battery()
    power_source_text = "Сеть" if not on_battery else "Батарея"
    label_power_source.config(text=f"Источник питания: {power_source_text}")

    if None not in previous_brightnesses:
        brightness_percentage = int(sum(previous_brightnesses) / brightness_avg_count)
    else:
        brightness_percentage = previous_brightnesses[-1]
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
    global previous_brightness, brightness_avg_count, interval_ac, interval_batt, brightness_adjust
    while running:
        # Определить источник питания
        on_battery = is_on_battery()
        # Таймаут на основе режима питания
        interval = int(entry_interval_ac.get()) if not on_battery else int(entry_interval_batt.get())

        # Множитель яркости
        brightness_adjust = int(scale_brightness_adjust.get())
        # debug(f"{'Сеть' if not on_battery else 'Батарея'}, таймаут: {interval} сек")

        # Сделать два замера с некоторым промежутком
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        # Вычисляем уровень яркости
        brightness = calculate_brightness(frame)
        brightness_percentage = int((brightness / 255) * 100)

        # Выравнивание, из-за нелинейной шкалы яркости в Windows 10
        brightness_percentage = int(max(0, min(100, brightness_percentage * (100 + brightness_adjust + brightness_offset) / 100)))

        # Берём среднее от трех последних замеров, для более плавного изменения
        if len(previous_brightnesses) < brightness_avg_count - 1:
            while (len(previous_brightnesses) < brightness_avg_count - 1):
                previous_brightnesses.append(brightness_percentage)
        elif len(previous_brightnesses) == brightness_avg_count:
            previous_brightnesses.pop(0)
        previous_brightnesses.append(brightness_percentage)

        brightness_percentage = int(sum(previous_brightnesses) / brightness_avg_count)

        i = 0
        string = ""
        while i < len(previous_brightnesses):
            string = f"{string + ", " if len(string) > 0 else ""}{previous_brightnesses[i]}"
            i = i + 1
        debug(string)

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
button_start_stop = ttk.Button(root, text="Старт", command=start_stop)
button_start_stop.pack(pady=15)

root.mainloop()