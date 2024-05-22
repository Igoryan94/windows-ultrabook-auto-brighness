import cv2
import numpy as np
import win32api
import win32con
import win32gui
import time
import psutil
import json
import os
import sys
import subprocess
import threading
import logging
import tkinter as tk
import tkinter.ttk as ttk
import ttkthemes as ttkthemes

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

program_version = 0.90

def debug(text):
    if getattr(sys, 'frozen', False):
        # Проект запущен как собранный exe-файл, нет отладки
        return
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
    # Вычитаем brightness_bright_background_offset, если режим "Яркий фон" включен
    if bright_background_var.get():
        brightness_to_set = max(5, brightness - brightness_bright_background_offset)
    else:
        brightness_to_set = max(5, brightness)

    # Вызываем PowerShell для изменения яркости
    command = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness_to_set})"
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

def on_graph_click(event):
        # Открываем файл конфига в блокноте
        os.startfile('config.json')

def save_config(event=None):
    with open('config.json', 'w') as f:
        config = {
            'interval_ac': int(entry_interval_ac.get()),
            'interval_batt': int(entry_interval_batt.get()),
            'brightness_adjust': scale_brightness_adjust.get(),
            'bright_background': bright_background_var.get(),
            'brightness_table': {str(k): v for k, v in brightness_table.items()}
        }
        json.dump(config, f, indent=4)

# Глобальные переменные
default_interval_ac = 12
default_interval_batt = 60
default_brightness_adjust = 50
default_brightness_table = {
    0: 48,
    25: 54,
    40: 58,
    55: 62,
    70: 64,
    85: 66,
    100: 68,
    115: 73,
    130: 79,
    145: 88,
    160: 95,
    190: 100
}

interval_ac = default_interval_ac
interval_batt = default_interval_batt
brightness_adjust = default_brightness_adjust
brightness_bright_background_offset = 0
brightness_table = default_brightness_table

brightness_avg_count = 3
previous_brightnesses = []
brightness_bright_background_offset_value = 13

brightness_offset = 3

ambient_brightness = 255

running = False

nid = 0

# Настройка логирования, если не релизный билд
if not getattr(sys, 'frozen', False):
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
config.setdefault('brightness_table', default_brightness_table)

# Сохранение конфигурации в файл
with open(config_file, 'w') as f:
    # сохраяем конфигурационный файл с обновленными значениями
    json.dump(config, f)

# Теперь можно использовать значения конфигурации
interval_ac = config['interval_ac']
interval_batt = config['interval_batt']
brightness_adjust = config['brightness_adjust']
brightness_table = config['brightness_table']

# Создаем интерфейс
root = tk.Tk()
root.title("UltraBook Auto Brightness")
root.geometry("800x400")

# Применяем тему
ttkthemes.themed_style = ttkthemes.ThemedStyle(root)
ttkthemes.themed_style.set_theme("vista")

# Создаем фрейм для интерфейса
interface_frame = ttk.Frame(root)
interface_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Настраиваем видимые элементы окна
label_power_source = ttk.Label(root, text="Источник питания:")
label_power_source.pack(in_=interface_frame, pady=(20, 0))

label_brightness = ttk.Label(root, text="Яркость дисплея:")
label_brightness.pack(in_=interface_frame)

label_ambient_brightness = ttk.Label(root, text="Окружающая яркость:")
label_ambient_brightness.pack(in_=interface_frame)

label_status = ttk.Label(root, text="Состояние:")
label_status.pack(in_=interface_frame, pady=(0, 10))

# Добавляем элементы для изменения параметров переменных
label_interval_ac = ttk.Label(root, text="Таймаут при питании от сети (сек):")
label_interval_ac.pack(in_=interface_frame)
entry_interval_ac = ttk.Entry(root, width=10)
entry_interval_ac.insert(0, str(interval_ac))
entry_interval_ac.pack(in_=interface_frame)
entry_interval_ac.bind('<KeyRelease>', save_config)

label_interval_batt = ttk.Label(root, text="Таймаут при питании от батареи (сек):")
label_interval_batt.pack(in_=interface_frame)
entry_interval_batt = ttk.Entry(root, width=10)
entry_interval_batt.insert(0, str(interval_batt))
entry_interval_batt.pack(in_=interface_frame)
entry_interval_batt.bind('<KeyRelease>', save_config)

frame_bright_background = ttk.Frame(root)
frame_bright_background.pack(in_=interface_frame, pady=(10, 0))

bright_background_var = tk.BooleanVar()
switch_bright_background = ttk.Checkbutton(frame_bright_background, variable=bright_background_var, command=save_config)
switch_bright_background.pack(side=tk.LEFT)

label_bright_background = ttk.Label(frame_bright_background, text="Режим \"Яркий объект на тёмном фоне\"")
label_bright_background.pack(side=tk.RIGHT)
label_bright_background.bind("<Button-1>", lambda event: bright_background_var.set(not bright_background_var.get()))

label_brightness_adjust = ttk.Label(root, text="Регулировка яркости (в процентах):")
label_brightness_adjust.pack(in_=interface_frame, pady=(10, 0))
scale_brightness_adjust = ttk.Scale(root, from_=0, to=100, orient=tk.HORIZONTAL, length=200, command=save_config)
scale_brightness_adjust.set(brightness_adjust)
scale_brightness_adjust.pack(in_=interface_frame)

# Создаем фрейм для графика
graph_frame = ttk.Frame(root)
graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Создаем график
fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot(111)
ax.set_title("Таблица яркости")
ax.set_xlabel("Окружающая яркость")
ax.set_ylabel("Яркость дисплея, %")
canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas.draw()
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
# TODO: доделать изменение таблицы кликами по нужным точкам графика
canvas.mpl_connect('button_release_event', on_graph_click)

def update_labels():
    global previous_brightnesses, brightness_avg_count, ambient_brightness
    on_battery = is_on_battery()
    power_source_text = "Сеть" if not on_battery else "Батарея"
    label_power_source.config(text=f"Источник питания: {power_source_text}")

    if None not in previous_brightnesses:
        if len(previous_brightnesses) > 1:
            brightness_percentage = previous_brightnesses[len(previous_brightnesses) - 1]
            label_brightness.config(text=f"Яркость дисплея: {brightness_percentage}%")

    label_ambient_brightness.config(text=f"Окружающая яркость: {ambient_brightness}")

    status_text = "Работает" if running else "Остановлен"
    label_status.config(text=f"Состояние: {status_text}")

    ax.clear()
    ax.set_title("Таблица brightness_table")
    ax.set_xlabel("Окружающая яркость")
    ax.set_ylabel("Яркость дисплея, %")
    ax.plot(list(brightness_table.keys()), list(brightness_table.values()))
    canvas.draw()

    root.after(1000, update_labels)

update_labels()

def on_closing():
    global running
    running = False
    show_in_tray(False)
    root.destroy()

def start_daemon():
    global running
    running = True
    threading.Thread(target=main_loop).start()
    show_in_tray(True)
    button_start_stop.config(text="Стоп")
    update_labels()
    root.iconify()

root.protocol("WM_DELETE_WINDOW", on_closing)

def main_loop():
    global previous_brightness, brightness_avg_count, interval_ac, interval_batt, brightness_adjust, brightness_bright_background_offset, brightness_table, ambient_brightness
    while running:
        # Определить источник питания
        on_battery = is_on_battery()
        # Таймаут на основе режима питания
        interval = int(entry_interval_ac.get()) if not on_battery else int(entry_interval_batt.get())

        # Множитель яркости
        brightness_adjust = int(scale_brightness_adjust.get())
        # debug(f"{'Сеть' if not on_battery else 'Батарея'}, таймаут: {interval} сек")

        # Делаем замер с камеры
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 70)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 70)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret, frame = cap.read()
        cap.release()

        # Вычисляем уровень яркости
        ambient_brightness = calculate_brightness(frame)

        # Интерполируем значение яркости в диапазоне от 0 до 100
        brightness_percentage = 0
        brightness_table_keys = sorted(brightness_table.keys())
        for i, key in enumerate(brightness_table_keys):
            if ambient_brightness <= int(key):
                brightness_percentage = brightness_table[key]
                break
            elif i == len(brightness_table_keys) - 1:
                brightness_percentage = brightness_table[key]
            else:
                next_key = brightness_table_keys[i + 1]
                if ambient_brightness >= int(next_key):
                    continue
                brightness_percentage = brightness_table[key] + (ambient_brightness - int(key)) * (brightness_table[next_key] - brightness_table[key]) / (int(next_key) - int(key))
                break

        # Если тумблер "Яркий фон" включен, устанавливаем brightness_bright_background_offset
        if bright_background_var.get():
            brightness_bright_background_offset = brightness_bright_background_offset_value
        else:
            brightness_bright_background_offset = 0

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
        string = f"Яркость сэмпла: {ambient_brightness}, список % яркости: {string}"
        debug(string)

        # Установить яркость дисплея, не ниже 5%
        set_display_brightness(int(brightness_percentage))

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
button_start_stop.pack(in_=interface_frame, pady=15)

start_daemon()
root.mainloop()