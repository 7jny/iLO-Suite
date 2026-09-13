import sys
import time
from typing import Dict, Any, List, Optional

class MacroSender:
    def __init__(self):
        pass

    def find_console_windows(self) -> List[Dict[str, Any]]:
        """Finds active iLO Remote Console windows on the desktop (Windows only)."""
        if sys.platform != "win32":
            return []

        import ctypes
        user32 = ctypes.windll.user32

        results = []

        def enum_windows_callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

            title_lower = title.lower()
            is_match = any(term in title_lower for term in [
                "hpe lights-out", "remote console", "ilo 3",
                "integrated remote console", "dvc console", "hplocons"
            ])

            if is_match:
                results.append({"hwnd": hwnd, "title": title})

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return results

    def send_keystroke_to_window(self, hwnd: int, macro: str) -> bool:
        """Injects a key combination into the specified window handle."""
        if sys.platform != "win32":
            return False

        import ctypes
        user32 = ctypes.windll.user32

        # Virtual Key Codes
        VK_CONTROL = 0x11
        VK_MENU = 0x12     # ALT
        VK_DELETE = 0x2E
        VK_SNAPSHOT = 0x2C # PrintScreen / SysRq
        VK_B = 0x42
        KEYEVENTF_KEYUP = 0x0002

        fkey_map = {
            "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
            "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
            "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B
        }

        # Bring console window to foreground
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.08)

        macro_upper = macro.upper().strip()

        if macro_upper in ("CAD", "CTRL_ALT_DEL", "CTRL+ALT+DEL"):
            # Send Ctrl+Alt+Del
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_DELETE, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_DELETE, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            # Also send Ctrl+T (Standard iLO Java Console Hotkey for CAD)
            time.sleep(0.04)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(0x54, 0, 0, 0) # 'T'
            time.sleep(0.04)
            user32.keybd_event(0x54, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            return True

        elif macro_upper in ("SYSRQ", "ALT_SYSRQ_B", "ALT+SYSRQ+B"):
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_SNAPSHOT, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(VK_SNAPSHOT, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_B, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(VK_B, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            return True

        elif macro_upper in fkey_map:
            vk = fkey_map[macro_upper]
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True

        return False

    def dispatch_macro(self, macro: str, ilo_client=None) -> Dict[str, Any]:
        """Dispatches a keyboard macro to active console windows and server firmware."""
        macro_clean = macro.upper().strip()
        windows = self.find_console_windows()
        sent_to_window = False
        target_title = None

        if windows:
            top_window = windows[0]
            target_title = top_window["title"]
            sent_to_window = self.send_keystroke_to_window(top_window["hwnd"], macro_clean)

        extra_info = ""
        # If F9 (BIOS Setup) was pressed, also arm RBSU one-time boot in iLO
        if macro_clean == "F9" and ilo_client:
            try:
                ilo_client.set_one_time_boot("RBSU")
                extra_info = " (RBSU BIOS Setup boot armed in iLO)"
            except Exception as e:
                extra_info = f" (Failed arming RBSU: {e})"

        # If F11 (Boot Menu) was pressed
        elif macro_clean == "F11" and ilo_client:
            extra_info = " (Boot Menu key sent)"

        msg = f"Keystroke [{macro_clean}] dispatched"
        if sent_to_window:
            msg += f" to '{target_title}'"
        else:
            msg += " (no console window currently active on desktop)"
        msg += extra_info

        print(f"[CONSOLE] {msg}")

        return {
            "success": True,
            "macro": macro_clean,
            "sent_to_window": sent_to_window,
            "window_title": target_title,
            "message": msg
        }

macro_sender = MacroSender()
