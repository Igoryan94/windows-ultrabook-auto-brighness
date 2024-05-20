import cv2
import numpy as np
import win32api
import win32con
import win32gui
import time
import psutil
import subprocess
import logging
import tkinter as tk
import threading

# Настройка логирования
logging.basicConfig(filename='autobrightness.log', level=logging.INFO)

# Глобальные переменные
previous_brightness = None
interval_ac = 12
interval_batt = 60
adjust_multiplier = 1.53
running = False

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

# Создаем иконку в системном трее
hWnd = win32gui.CreateWindow("STATIC", "", win32con.WS_OVERLAPPED | win32con.WS_SYSMENU, 0, 0, 0, 0, 0, 0, None, None)
icon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, 0, 0, win32con.LR_DEFAULTSIZE | win32con.LR_SHARED)
nid = (hWnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP, win32con.WM_USER + 20, icon, "autobrightness")
win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

# Создаем интерфейс
root = tk.Tk()
root.title("Auto Brightness")
root.geometry("300x235")

label_power_source = tk.Label(root, text="Источник питания:")
label_power_source.pack()

label_brightness = tk.Label(root, text="Яркость дисплея:")
label_brightness.pack()

label_status = tk.Label(root, text="Статус:")
label_status.pack()

# Добавляем поля для изменения параметров переменных
label_interval_ac = tk.Label(root, text="Таймаут при питании от сети (сек):")
label_interval_ac.pack()
entry_interval_ac = tk.Entry(root, width=10)
entry_interval_ac.insert(0, str(interval_ac))
entry_interval_ac.pack()

label_interval_batt = tk.Label(root, text="Таймаут при питании от батареи (сек):")
label_interval_batt.pack()
entry_interval_batt = tk.Entry(root, width=10)
entry_interval_batt.insert(0, str(interval_batt))
entry_interval_batt.pack()

label_adjust_multiplier = tk.Label(root, text="Коэффициент коррекции яркости:")
label_adjust_multiplier.pack()
entry_adjust_multiplier = tk.Entry(root, width=10)
entry_adjust_multiplier.insert(0, str(adjust_multiplier))
entry_adjust_multiplier.pack()

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

    status_text = "Работает" if brightness_percentage is not None else "Остановлен"
    label_status.config(text=f"Статус: {status_text}")

    root.after(1000, update_labels)

update_labels()

def on_closing():
    global running
    running = False
    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
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
        brightness_percentage = min(100, int(brightness_percentage * adjust_multiplier))

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

def start_stop():
    global running
    if not running:
        running = True
        threading.Thread(target=main_loop).start()
        button_start_stop.config(text="Стоп")
    else:
        running = False
        button_start_stop.config(text="Старт")
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)

# Кнопка "Старт/стоп"
button_start_stop = tk.Button(root, text="Старт", command=start_stop)
button_start_stop.pack(padx=10, pady=(5, 20))

root.mainloop()