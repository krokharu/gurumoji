import ctypes
from ctypes import wintypes
import sys
import time


def main() -> None:
    hwnd, relative_x, relative_y = map(int, sys.argv[1:4])
    user32 = ctypes.windll.user32
    title_buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
    if "Colab" not in title_buffer.value:
        raise RuntimeError(f"Expected Colab browser window, got: {title_buffer.value!r}")
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError(f"Window not found: {hwnd}")
    if not user32.SetForegroundWindow(hwnd):
        raise RuntimeError("Could not focus Colab browser window")
    time.sleep(0.2)
    user32.SetCursorPos(rect.left + relative_x, rect.top + relative_y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    print(f"Clicked {title_buffer.value!r} at ({relative_x}, {relative_y})")


if __name__ == "__main__":
    main()
