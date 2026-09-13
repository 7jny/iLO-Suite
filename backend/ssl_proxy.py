import os
import sys
import shutil
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from typing import Optional

class IloSSLProxy:
    """
    High-performance TLS 1.0 Bridge using Java 21 SunJSSE engine.
    Supports ancient ciphers (including 3DES and RC4) and disables TLS extensions,
    allowing seamless communication with ancient iLO 3 servers on Windows 11.
    """
    def __init__(self, listen_port: int = 8089, https_port: int = 8443):
        self.listen_port = listen_port
        self.https_port = https_port
        self.target_host = "127.0.0.1"
        self.target_port = 443
        self.proc = None
        self.lock = threading.RLock()
        self.active = False
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.console_jar = os.path.join(self.root_dir, "console", "bin", "ilo3-console.jar")
        self.legacy_security = os.path.join(self.root_dir, "console", "legacy.security")

    def set_target(self, host: str, port: int = 443):
        clean_host = host.replace("http://", "").replace("https://", "").split(":")[0].strip()
        with self.lock:
            self.target_host = clean_host
            self.target_port = port

            # If already running, notify running bridge of target change
            if self.active and self._is_alive():
                try:
                    url = f"http://127.0.0.1:{self.listen_port}/__bridge_set_target?host={urllib.parse.quote(clean_host)}&port={port}"
                    with urllib.request.urlopen(url, timeout=2) as resp:
                        pass
                except Exception:
                    pass

    def start(self):
        with self.lock:
            if self.active and self._is_alive():
                self.set_target(self.target_host, self.target_port)
                return

            java_exe = shutil.which("javaw") or shutil.which("java")
            if not java_exe:
                raise FileNotFoundError("Java runtime not found for TLS Bridge")

            if not os.path.exists(self.console_jar):
                raise FileNotFoundError(f"Console JAR not found: {self.console_jar}")

            cmd = [
                java_exe,
                f"-Djava.security.properties={os.path.abspath(self.legacy_security)}",
                "-Djdk.tls.client.disableExtensions=true",
                "-Dsun.security.ssl.allowUnsafeRenegotiation=true",
                "-cp",
                os.path.abspath(self.console_jar),
                "util.TlsBridge",
                self.target_host,
                str(self.target_port),
                str(self.listen_port),
                str(self.https_port)
            ]

            creation_flags = 0
            if sys.platform == "win32":
                # CREATE_NO_WINDOW ensures zero visible console window while keeping process in tree
                creation_flags = 0x08000000

            print(f"[IloSSLProxy] Spawning Java TLS Bridge on port {self.listen_port} for {self.target_host}:{self.target_port}...")
            self.proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(self.console_jar),
                creationflags=creation_flags,
                close_fds=True
            )

            # Wait for bridge to come online
            for _ in range(25):
                time.sleep(0.2)
                if self._is_alive():
                    self.active = True
                    print(f"[IloSSLProxy] Java TLS Bridge online at http://127.0.0.1:{self.listen_port}")
                    return

            self.active = True

    def _is_alive(self) -> bool:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.listen_port}/__bridge_set_target")
            with urllib.request.urlopen(req, timeout=1) as resp:
                return resp.status == 200
        except Exception:
            return False

    def stop(self):
        with self.lock:
            # 1. Send clean HTTP shutdown request to Java Bridge
            try:
                url = f"http://127.0.0.1:{self.listen_port}/__bridge_shutdown"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=1) as resp:
                    pass
            except Exception:
                pass

            # 2. Terminate tracked subprocess
            if self.proc:
                pid = self.proc.pid
                try:
                    self.proc.terminate()
                except Exception:
                    pass
                try:
                    self.proc.kill()
                except Exception:
                    pass

                if sys.platform == "win32":
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=2)
                    except Exception:
                        pass
                self.proc = None

            # 3. Kill any lingering process listening on bridge ports (8089, 8443)
            if sys.platform == "win32":
                try:
                    cmd = f'powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort {self.listen_port},{self.https_port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=3)
                except Exception:
                    pass

            self.active = False

    def get_url(self) -> str:
        return f"http://127.0.0.1:{self.listen_port}"

    def get_https_url(self) -> str:
        return f"https://127.0.0.1:{self.https_port}"

    def get_https_target(self) -> str:
        return f"127.0.0.1:{self.https_port}"

ilo_ssl_proxy = IloSSLProxy(listen_port=8089, https_port=8443)
