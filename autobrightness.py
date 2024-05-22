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

program_version = 0.91

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
    # Множитель яркости
    brightness_adjust = int(scale_brightness_adjust.get())

    # Вычитаем brightness_bright_background_offset, если режим "Яркий фон" включен
    if bright_background_var.get():
        brightness_to_set = max(5, brightness - brightness_bright_background_offset)
    else:
        brightness_to_set = max(5, brightness)
    brightness_to_set = brightness_to_set * brightness_adjust / 50

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

def save_config(event=None):
    with open('config.json', 'w') as f:
        config = {
            'interval_ac': int(entry_interval_ac.get()),
            'interval_batt': int(entry_interval_batt.get()),
            'brightness_adjust': int(scale_brightness_adjust.get()),
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
root.geometry("560x450")

# Применяем тему
ttkthemes.themed_style = ttkthemes.ThemedStyle(root)
ttkthemes.themed_style.set_theme("vista")

# Создаем фрейм для интерфейса
interface_frame = ttk.Frame(root)
interface_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Настраиваем видимые элементы окна
label_power_source = ttk.Label(root, text="Источник питания:")
label_power_source.pack(in_=interface_frame, pady=(20, 0))

label_ambient_brightness = ttk.Label(root, text="Окружающая яркость:")
label_ambient_brightness.pack(in_=interface_frame)

label_brightness = ttk.Label(root, text="Яркость дисплея:")
label_brightness.pack(in_=interface_frame)

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

# Кнопка "Открыть конфиг"
button_open_config = ttk.Button(root, text="Открыть конфиг", command=lambda: os.startfile("config.json"))
button_open_config.pack(in_=interface_frame, pady=(20, 0))

# Кнопка "Загрузить параметры из конфига"
def load_config_params():
    global interval_ac, interval_batt, brightness_adjust, brightness_table
    with open('config.json', 'r') as f:
        config = json.load(f)
    interval_ac = config['interval_ac']
    interval_batt = config['interval_batt']
    brightness_adjust = config['brightness_adjust']
    brightness_table = config['brightness_table']
    entry_interval_ac.delete(0, tk.END)
    entry_interval_ac.insert(0, str(interval_ac))
    entry_interval_batt.delete(0, tk.END)
    entry_interval_batt.insert(0, str(interval_batt))
    scale_brightness_adjust.set(brightness_adjust)
    save_config()

button_load_config = ttk.Button(root, text="Загрузить параметры из конфига", command=load_config_params)
button_load_config.pack(in_=interface_frame, pady=(0, 20))

# Создание фрейма для таблицы
table_frame = ttk.Frame(root)
table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Создание таблицы
table = ttk.Treeview(table_frame, columns=("brightness", "display_brightness"))
table.column("#0", width=0, stretch=tk.NO)
table.pack(fill=tk.BOTH, expand=True)

# Настройка заголовков столбцов
table.heading("brightness", text="Окружающая яркость", anchor=tk.CENTER)
table.heading("display_brightness", text="Яркость дисплея, %", anchor=tk.CENTER)

# Настройка ширины столбцов
table.column("brightness", minwidth=100, width=100, stretch=tk.YES)
table.column("display_brightness", minwidth=100, width=100, stretch=tk.YES)
table.rowconfigure(0, weight=1)

# Функция для выравнивания столбцов
def resize_columns(event):
    table.column("brightness", width=table.winfo_width() // 2, anchor=tk.CENTER)
    table.column("display_brightness", width=table.winfo_width() // 2, anchor=tk.CENTER)

# Привязываем функцию к событию изменения размера окна
table.bind("<Configure>", resize_columns)
# resize_columns("")

# Функции для работы с таблицей
def add_row():
    table.insert("", "end", values=(entry_table_ambient_brightness.get(), entry_table_display_brightness.get()), tags=("center",))
    brightness_table[entry_table_ambient_brightness.get()] = int(entry_table_display_brightness.get())
    save_config()

def delete_row():
    selected = table.selection()
    if selected:
        key = table.item(selected[0], "values")[0]
        del brightness_table[key]
        table.delete(selected[0])
        save_config()

def edit_row(event):
    selected = table.selection()
    if selected:
        old_key = table.item(selected[0], "values")[0]
        new_key = entry_table_ambient_brightness.get()
        new_value_str = entry_table_display_brightness.get()
        if new_value_str:
            new_value = int(new_value_str)
            brightness_table[new_key] = new_value
            del brightness_table[old_key]
            table.item(selected[0], values=(new_key, new_value), tags=("center",))
            save_config()
        else:
            # Если значение пустое, выводим сообщение об ошибке или игнорируем изменение
            debug("Значение яркости дисплея не может быть пустым.")

# Кнопки для работы с таблицей
button_add = ttk.Button(table_frame, text="Добавить", command=add_row)
button_add.pack(side=tk.TOP, pady=5)

button_delete = ttk.Button(table_frame, text="Удалить", command=delete_row)
button_delete.pack(side=tk.TOP, pady=5)

# Поля для ввода значений для редактирования
label_table_ambient_brightness = ttk.Label(table_frame, text="Окружающая яркость:")
label_table_ambient_brightness.pack(side=tk.TOP, pady=5)
entry_table_ambient_brightness = ttk.Entry(table_frame)
entry_table_ambient_brightness.pack(side=tk.TOP, pady=5)

label_table_display_brightness = ttk.Label(table_frame, text="Яркость дисплея, %:")
label_table_display_brightness.pack(side=tk.TOP, pady=5)
entry_table_display_brightness = ttk.Entry(table_frame)
entry_table_display_brightness.pack(side=tk.TOP, pady=5)

table.bind("<Double-1>", edit_row)

# Обновление интерфейса
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

    # Заполнение таблицы из brightness_table
    table.delete(*table.get_children())
    for key, value in brightness_table.items():
        table.insert("", "end", values=(key, value))

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
    global previous_brightness, brightness_avg_count, interval_ac, interval_batt, brightness_bright_background_offset, brightness_table, ambient_brightness
    while running:
        # Определить источник питания
        on_battery = is_on_battery()
        # Таймаут на основе режима питания
        interval = int(entry_interval_ac.get()) if not on_battery else int(entry_interval_batt.get())

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
                brightness_percentage = int(brightness_table[key])
                break
            elif i == len(brightness_table_keys) - 1:
                brightness_percentage = int(brightness_table[key])
            else:
                next_key = brightness_table_keys[i + 1]
                if ambient_brightness >= int(next_key):
                    continue
                brightness_percentage = int(brightness_table[key] + (ambient_brightness - int(key)) * (brightness_table[next_key] - brightness_table[key]) / (int(next_key) - int(key)))
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