import os
import sys
import shutil
import subprocess
from typing import Optional, Dict, Any

HPLOCONS_PATHS = [
    # HPE iLO Integrated Remote Console (Standard Windows 10/11)
    r"C:\Program Files (x86)\Hewlett Packard Enterprise\HPE iLO Integrated Remote Console\HPLOCONS.exe",
    r"C:\Program Files\Hewlett Packard Enterprise\HPE iLO Integrated Remote Console\HPLOCONS.exe",
    r"C:\Program Files (x86)\HP\HPE iLO Integrated Remote Console\HPLOCONS.exe",
    r"C:\Program Files\HP\HPE iLO Integrated Remote Console\HPLOCONS.exe",
    # HP Lights-Out Standalone Remote Console (Older naming)
    r"C:\Program Files (x86)\Hewlett-Packard\HP Lights-Out Standalone Remote Console\HPLOCONS.exe",
    r"C:\Program Files\Hewlett-Packard\HP Lights-Out Standalone Remote Console\HPLOCONS.exe",
    r"C:\Program Files (x86)\Hewlett Packard Enterprise\HP Lights-Out Standalone Remote Console\HPLOCONS.exe",
    r"C:\Program Files\Hewlett Packard Enterprise\HP Lights-Out Standalone Remote Console\HPLOCONS.exe",
    r"C:\Program Files (x86)\HP\HP Lights-Out Standalone Remote Console\HPLOCONS.exe",
    r"C:\Program Files\HP\HP Lights-Out Standalone Remote Console\HPLOCONS.exe"
]

def spawn_on_user_desktop(cmd_line: str, cwd: Optional[str] = None) -> int:
    """Launches a GUI process explicitly on the interactive user desktop (WinSta0\\Default).
    This ensures windows appear on the physical screen even when the parent server
    process is running inside a background task or isolated virtual desktop station."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class STARTUPINFOW(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('lpReserved', wintypes.LPWSTR),
                    ('lpDesktop', wintypes.LPWSTR),
                    ('lpTitle', wintypes.LPWSTR),
                    ('dwX', wintypes.DWORD),
                    ('dwY', wintypes.DWORD),
                    ('dwXSize', wintypes.DWORD),
                    ('dwYSize', wintypes.DWORD),
                    ('dwXCountChars', wintypes.DWORD),
                    ('dwYCountChars', wintypes.DWORD),
                    ('dwFillAttribute', wintypes.DWORD),
                    ('dwFlags', wintypes.DWORD),
                    ('wShowWindow', wintypes.WORD),
                    ('cbReserved2', wintypes.WORD),
                    ('lpReserved2', ctypes.c_void_p),
                    ('hStdInput', wintypes.HANDLE),
                    ('hStdOutput', wintypes.HANDLE),
                    ('hStdError', wintypes.HANDLE),
                ]

            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('hProcess', wintypes.HANDLE),
                    ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD),
                    ('dwThreadId', wintypes.DWORD),
                ]

            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(STARTUPINFOW)
            si.lpDesktop = r"WinSta0\Default"
            si.dwFlags = 1  # STARTF_USESHOWWINDOW
            si.wShowWindow = 1  # SW_SHOWNORMAL

            pi = PROCESS_INFORMATION()

            # CREATE_NEW_PROCESS_GROUP = 0x00000200
            res = ctypes.windll.kernel32.CreateProcessW(
                None,
                cmd_line,
                None,
                None,
                False,
                0x00000200,
                None,
                cwd,
                ctypes.byref(si),
                ctypes.byref(pi)
            )
            if res:
                pid = pi.dwProcessId
                ctypes.windll.kernel32.CloseHandle(pi.hThread)
                ctypes.windll.kernel32.CloseHandle(pi.hProcess)
                return pid
            else:
                err = ctypes.GetLastError()
                print(f"[ConsoleLauncher] CreateProcessW failed with error {err}")
        except Exception as e:
            print(f"[ConsoleLauncher] spawn_on_user_desktop error: {e}")

    # Fallback
    proc = subprocess.Popen(
        cmd_line,
        cwd=cwd,
        shell=True if isinstance(cmd_line, str) else False,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    return proc.pid


class ConsoleLauncher:
    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.console_jar = os.path.join(self.root_dir, "console", "bin", "ilo3-console.jar")
        self.legacy_security = os.path.join(self.root_dir, "console", "legacy.security")
        self._cached_hplocons_path: Optional[str] = None
        self.launched_pids = set()

    def kill_all(self):
        """Kills all console windows spawned during this session."""
        for pid in list(self.launched_pids):
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=2)
            except Exception:
                pass
        self.launched_pids.clear()
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "HPLOCONS.exe"], capture_output=True, timeout=2)
            except Exception:
                pass

    def find_hplocons(self) -> Optional[str]:
        """Checks if HP / HPE Lights-Out Standalone Remote Console is installed on Windows."""
        if self._cached_hplocons_path and os.path.isfile(self._cached_hplocons_path):
            return self._cached_hplocons_path

        # 1. Check known file paths
        for path in HPLOCONS_PATHS:
            if os.path.isfile(path):
                self._cached_hplocons_path = path
                return path

        # 2. Check PATH environment
        which_path = shutil.which("HPLOCONS.exe") or shutil.which("HPLOCONS")
        if which_path and os.path.isfile(which_path):
            self._cached_hplocons_path = which_path
            return which_path

        # 3. Check Windows Registry App Paths
        if sys.platform == "win32":
            try:
                import winreg
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\HPLOCONS.exe"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\HPLOCONS.exe"),
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\HPLOCONS.exe")
                ]
                for root_key, sub_key in reg_paths:
                    try:
                        with winreg.OpenKey(root_key, sub_key) as key:
                            val, _ = winreg.QueryValueEx(key, "")
                            if val and os.path.isfile(val):
                                self._cached_hplocons_path = val
                                return val
                    except (FileNotFoundError, OSError):
                        pass
            except Exception:
                pass

        # 4. Check user AppData Local / Roaming ClickOnce or App locations
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            common_appdata_paths = [
                os.path.join(local_appdata, "Apps", "2.0"),
                os.path.join(local_appdata, "Hewlett Packard Enterprise"),
                os.path.join(local_appdata, "Hewlett-Packard")
            ]
            for base in common_appdata_paths:
                if os.path.isdir(base):
                    for root, _, files in os.walk(base):
                        if "HPLOCONS.exe" in files:
                            candidate = os.path.join(root, "HPLOCONS.exe")
                            if os.path.isfile(candidate):
                                self._cached_hplocons_path = candidate
                                return candidate

        return None

    def launch_java_console(self, host: str, user: str, password: str, session_key: Optional[str] = None) -> Dict[str, Any]:
        """Launches the compiled standalone iLO 3 console with Java 21 & legacy SSL config on user desktop."""
        java_exe = shutil.which("javaw") or shutil.which("java")
        if not java_exe:
            raise FileNotFoundError("Java executable ('java' or 'javaw') was not found on this system.")

        if not os.path.isfile(self.console_jar):
            raise FileNotFoundError(f"Console JAR not found: {self.console_jar}. Please compile it first.")

        if not os.path.isfile(self.legacy_security):
            raise FileNotFoundError(f"Legacy security file not found: {self.legacy_security}")

        # Clean host (strip protocol)
        clean_host = host.replace("http://", "").replace("https://", "").split(":")[0].strip()

        cmd_parts = [
            f'"{java_exe}"',
            f'-Djava.security.properties="{os.path.abspath(self.legacy_security)}"',
            '-Djdk.tls.client.disableExtensions=true',
            '-Dsun.security.ssl.allowUnsafeRenegotiation=true',
            '-Dhttps.protocols=TLSv1,TLSv1.1,TLSv1.2',
            '-jar',
            f'"{os.path.abspath(self.console_jar)}"',
            clean_host,
            user,
            f'"{password}"' if password else '""'
        ]

        if session_key:
            cmd_parts.extend(["--session-key", session_key])

        cmd_line = " ".join(cmd_parts)
        print(f"[ConsoleLauncher] Launching Java console on user desktop for {clean_host} as {user}...")

        pid = spawn_on_user_desktop(cmd_line, cwd=os.path.dirname(self.console_jar))
        if pid:
            self.launched_pids.add(pid)

        return {
            "success": True,
            "type": "java_console",
            "pid": pid,
            "host": clean_host
        }

    def launch_hplocons(self, host: str, user: str, password: str, port: int = 443) -> Dict[str, Any]:
        """Launches HPE Lights-Out Standalone Remote Console on user desktop."""
        hplocons_path = self.find_hplocons()
        if not hplocons_path:
            raise FileNotFoundError("HPLOCONS.exe is not installed on this computer.")

        clean_host = host.replace("http://", "").replace("https://", "").strip().rstrip("/")
        if ":" in clean_host:
            server_arg = clean_host
        elif port and port != 443:
            server_arg = f"{clean_host}:{port}"
        else:
            server_arg = clean_host

        print(f"[ConsoleLauncher] Launching HPLOCONS on user desktop: {hplocons_path} -addr {server_arg} -name {user}")

        # Kill any frozen/stale previous HPLOCONS processes so slavesMutex is cleanly released
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "HPLOCONS.exe"], capture_output=True, timeout=2)
            except Exception:
                pass

        cmd_parts = [
            f'"{hplocons_path}"',
            '-addr', server_arg
        ]
        if user:
            cmd_parts.extend(['-name', f'"{user}"'])
        if password:
            cmd_parts.extend(['-password', f'"{password}"'])

        cmd_line = " ".join(cmd_parts)
        pid = spawn_on_user_desktop(cmd_line)
        if pid:
            self.launched_pids.add(pid)

        return {
            "success": True,
            "type": "hplocons",
            "pid": pid,
            "host": server_arg,
            "path": hplocons_path
        }

    def get_html5_url(self, host: str, port: int = 443) -> str:
        """Returns standard HTML5 remote console URL for iLO 4/5."""
        clean_host = host.replace("http://", "").replace("https://", "").split(":")[0].strip()
        port_suffix = f":{port}" if port != 443 else ""
        return f"https://{clean_host}{port_suffix}/html5/index.html"
