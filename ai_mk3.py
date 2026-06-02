import io
import threading
import tkinter as tk
import keyboard
import pyautogui
import pygetwindow as gw
from google import genai
from PIL import Image
import ctypes
import ctypes.wintypes
import sys
import os

API_KEY = "YOUR_API_KEY_HERE"
client = genai.Client(api_key=API_KEY)

current_popup = None
_analysis_thread = None  # FIX 1: track the thread

# Hide the console window from the taskbar
hwnd = ctypes.windll.kernel32.GetConsoleWindow()
ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE

def kill_app():
    print("[AI] Kill switch triggered. Shutting down...")
    destroy_popup()
    keyboard.unhook_all()
    os._exit(0)  # Force kills the process immediately

def destroy_popup():
    global current_popup
    if current_popup is not None:
        try:
            current_popup.after(0, current_popup.destroy)
        except Exception:
            pass
        current_popup = None
        print("Popup closed.")

def show_popup(text):
    global current_popup
    destroy_popup()

    root = tk.Tk()
    current_popup = root
    root.title("AI Debugger")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.config(bg="black")
    root.wm_attributes("-transparentcolor", "black")

    popup_width, popup_height = 320, 180
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_position = screen_width - popup_width - 30
    y_position = screen_height - popup_height - 50
    root.geometry(f"{popup_width}x{popup_height}+{x_position}+{y_position}")

    text_box = tk.Text(
        root, wrap="word", fg="#35373c", bg="black",
        font=("Consolas", 10, "bold"), bd=0, highlightthickness=0
    )
    text_box.insert("1.0", text)
    text_box.config(state="disabled")
    text_box.pack(fill="both", expand=True, padx=5, pady=5)

    help_label = tk.Label(root, text="[ESC]", fg="#71717a", bg="black", font=("Consolas", 8))
    help_label.pack(anchor="e", padx=5, pady=2)

    # FIX 2: cancel the after() reference so it doesn't fire on a dead window
    _auto_close = root.after(25000, destroy_popup)

    def on_close():
        try:
            root.after_cancel(_auto_close)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    current_popup = None  # Clear ref once mainloop exits naturally

# ORIGINAL FUNCTION (Bound to L)
def analyze_screen():
    global _analysis_thread
    print("\nShortcut triggered")
    img_byte_arr = None
    try:
        active_win = gw.getActiveWindow()
        if active_win is None:
            return

        bbox = (active_win.left, active_win.top, active_win.width, active_win.height)
        screenshot = pyautogui.screenshot(region=bbox)

        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        with Image.open(img_byte_arr) as image:
            image.load()
            prompt_message = [
                image,
                "Look at this window. Identify the asked question., "
                "Output ONLY the direct answer to the asked question, correction, or fixed code block, do not output the asked question. "
                "Do not include any introductions, conversational text, explanations, "
                "or markdown formatting blocks like ```python. Just provide the raw answer."
                " ONLY if the question is to match something you number the first collum with numbers starting from 1 and the second collum with letter from the alphabet then you tell me 1 a 2b 3c etc based on your search"
            ]
            try:
                print("3.5 Flash...")
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt_message
                )
            except Exception as primary_error:
                if "503" in str(primary_error):
                    print(" Fallback to 2.5 Flash...")
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt_message
                    )
                else:
                    raise primary_error

        show_popup(response.text)

    except Exception as e:
        print(f"Error: {str(e)}")
        show_popup("Error both busy")
    finally:
        # FIX 3: always close the buffer
        if img_byte_arr is not None:
            img_byte_arr.close()
        _analysis_thread = None  # Allow new thread after this one finishes

# NEW SEPARATE FUNCTION (Bound to P with Pro -> 3.5 -> 2.5 cascading fallbacks)
def analyze_screen_pro():
    global _analysis_thread
    print("\n[AI Pro] Shortcut triggered! Capturing active window...")
    img_byte_arr = None
    try:
        active_win = gw.getActiveWindow()
        if active_win is None:
            return

        bbox = (active_win.left, active_win.top, active_win.width, active_win.height)
        screenshot = pyautogui.screenshot(region=bbox)

        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        with Image.open(img_byte_arr) as image:
            image.load()
            prompt_message = [
                image,
                "Look at this window. Identify the asked question., "
                "Output ONLY the direct answer to the asked question, correction, or fixed code block, do not output the asked question. "
                "Do not include any introductions, conversational text, explanations, "
                "or markdown formatting blocks like ```python. Just provide the raw answer."
                " ONLY if the question is to match something you number the first collum with numbers starting from 1 and the second collum with letter from the alphabet then you tell me 1 a 2b 3c etc based on your search"
            ]
            
            try:
                print("3.1 Pro...")
                response = client.models.generate_content(
                    model="gemini-3.1-pro-preview",
                    contents=prompt_message
                )
            except Exception as e1:
                try:
                    print(f" 3.1 Pro issue: {str(e1)}. Fallback to 3.5 Flash...")
                    response = client.models.generate_content(
                        model="gemini-3.5-flash",
                        contents=prompt_message
                    )
                except Exception as e2:
                    print(f"3.5 Flash issue: {str(e2)}. Fallback to 2.5 Flash...")
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt_message
                    )

        show_popup(response.text)

    except Exception as e:
        print(f"Error: {str(e)}")
        show_popup("Error all models busy")
    finally:
        if img_byte_arr is not None:
            img_byte_arr.close()
        _analysis_thread = None

def on_hotkey():
    global _analysis_thread
    if _analysis_thread is not None and _analysis_thread.is_alive():
        print("Already processing skipping")
        return
    _analysis_thread = threading.Thread(target=analyze_screen, daemon=True)
    _analysis_thread.start()

def on_hotkey_pro():
    global _analysis_thread
    if _analysis_thread is not None and _analysis_thread.is_alive():
        print("Already processing skipping")
        return
    _analysis_thread = threading.Thread(target=analyze_screen_pro, daemon=True)
    _analysis_thread.start()

print("=" * 50)
print("  AI Invisible Coding Assistant is Live!")
print("  Press 'L' for standard flash mode.")
print("  Press 'P' for heavy Pro mode with fallbacks.")
print("  ESC to close popup.")
print("=" * 50)

keyboard.add_hotkey('L', on_hotkey)
keyboard.add_hotkey('P', on_hotkey_pro)
keyboard.add_hotkey('C', destroy_popup)
keyboard.add_hotkey('ctrl+shift+k', kill_app)
keyboard.wait()