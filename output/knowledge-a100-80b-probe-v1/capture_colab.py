import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time

from PIL import ImageGrab


class LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def main() -> None:
    hwnd = int(sys.argv[1])
    destination = Path(sys.argv[2])
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError(f"Window not found: {hwnd}")
    mode = sys.argv[3] if len(sys.argv) > 3 else ""
    foreground = None
    if mode == "--focus-if-idle":
        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(info)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        idle_seconds = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000
        if idle_seconds < 10:
            print(f"Skipped capture; user input {idle_seconds:.1f}s ago")
            return
        foreground = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
    if mode == "--window":
        image = ImageGrab.grab(window=hwnd)
    else:
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
    image.save(destination)
    if foreground and foreground != hwnd:
        ctypes.windll.user32.SetForegroundWindow(foreground)
    print(destination)


if __name__ == "__main__":
    main()
