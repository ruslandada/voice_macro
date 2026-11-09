import tkinter as tk
import ctypes
from ctypes import windll
import time
import os
import vosk
import sounddevice as sd
import queue
import json
import threading
import sys
from vk_names import vk_name, vk_normalize
from pynput import keyboard as pynput_keyboard

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Файлы")
q = queue.Queue()
try:
    model_name = os.listdir("model")[0]
    model = vosk.Model(f"model/{model_name}")
except Exception:
    sys.exit(1)
rec = vosk.KaldiRecognizer(model, 16000)
user = windll.user32
key = None
keys = []
prev = {}

_active_listener = None

def press_keys(vk_codes):
    for vk in vk_codes:
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    time.sleep(0.05)
    for vk in vk_codes:
        ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)
        time.sleep(0.02)

def parse_keys(content):
    try:
        start = content.index("[")
        end = content.index("]")
        return [int(x.strip()) for x in content[start + 1:end].split(",") if x.strip()]
    except (ValueError, IndexError):
        return []

def check_and_press(text):
    if not text:
        return
    name = text.strip() + ".txt"
    path = os.path.join(FOLDER, name)
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    vk_codes = parse_keys(content)
    if vk_codes:
        threading.Thread(target=press_keys, args=(vk_codes,), daemon=True).start()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

def listen():
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
            channels=1, callback=callback):
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result()).get("text", "")
                if text:
                    label_text.config(text=text)
                    check_and_press(text)

def load_files():
    result = []
    for name in os.listdir(FOLDER):
        path = os.path.join(FOLDER, name)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        result.append((name, content))
    return result

def delete_file(name):
    os.remove(os.path.join(FOLDER, name))
    refresh()

def refresh():
    for w in files_frame.winfo_children():
        w.destroy()

    for name, content in load_files():
        row = tk.Frame(files_frame, pady=3)
        row.pack(fill="x")
        left = tk.Frame(row)
        left.pack(side="left", fill="x", expand=True, padx=5)

        tk.Label(left, text=name, anchor="w", width=40).pack(anchor="w")
        tk.Label(left, text=content, anchor="w", justify="left", fg="#555").pack(anchor="w", side="left", padx=(20, 0))

        tk.Button(row, text="Удалить", fg="white", bg="#c0392b",
                  command=lambda n=name: delete_file(n)).pack(side="right", padx=5)

def file(name, content):
    path = os.path.join("файлы", name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(content))

def triger_file():
    if not keys:
        label.config(text="назначьте кнопки")
        return
    name = enter.get().strip()
    if not name:
        label.config(text="введите тригер")
        return
    content = "коды кнопок [" + ", ".join(str(k) for k in keys) + "]"
    file(name=name + ".txt", content=content)
    refresh()

def _stop_listener():
    global _active_listener
    if _active_listener is not None:
        try:
            _active_listener.stop()
        except Exception:
            pass
        _active_listener = None

def new_key():
    global _active_listener

    _stop_listener()

    keys.clear()
    prev.clear()
    labelk.config(text="Нажмите клавишу (Esc — отмена)")

    def on_press(k):
        if k == pynput_keyboard.Key.esc:
            _stop_listener()
            root.after(0, lambda: labelk.config(text="Отменено"))
            return False

        vk = getattr(k, "vk", None)
        if vk is None:
            v = getattr(k, "value", None)
            vk = getattr(v, "vk", None)
        if vk is None:
            return
        if vk == 0x01:
            return
        if vk not in keys:
            keys.append(vk)
            names = []
            for kk in keys:
                try:
                    names.append(vk_name(kk))
                except Exception:
                    names.append(str(kk))
            root.after(0, lambda n=" + ".join(names): labelk.config(text="keys: " + n))

    def on_release(k):
        if k == pynput_keyboard.Key.esc:
            return
        _stop_listener()

    listener = pynput_keyboard.Listener(
        on_press=on_press,
        on_release=on_release,
        suppress=True
    )
    _active_listener = listener
    listener.start()

root = tk.Tk()
root.title("просто файл")
root.geometry("800x600")

label = tk.Label(root, text="укажите клавиши и слово тригер")
label.pack()

labelk = tk.Label(root, text="кнопка не назначена")
labelk.pack()

button = tk.Button(root, text="назначить кнопку", command=new_key)
button.pack(pady=10)

labelinf = tk.Label(root, text="тригер")
labelinf.pack()

enter = tk.Entry(root, width=50)
enter.pack(pady=10)

buttonf = tk.Button(root, text="Создать файл", command=triger_file)
buttonf.pack(pady=10)

label_text = tk.Label(root, text="говорите...", font=("", 15))
label_text.pack()

tk.Button(root, text="обновить", command=refresh).pack()

files_frame = tk.Frame(root)
files_frame.pack(fill="both", expand=True, padx=10, pady=10)

refresh()

def _on_close():
    _stop_listener()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", _on_close)

threading.Thread(target=listen, daemon=True).start()

root.mainloop()