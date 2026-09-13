import os
import re
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

class ThreadedVMediaHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class VirtualMediaServer:
    def __init__(self, port=8088):
        self.port = port
        self.server = None
        self.thread = None
        self.mounted_file = None
        self.mounted_name = None
        self.lock = threading.RLock()
        self.active = False
        self.bind_ip = "0.0.0.0"

    def get_lan_ip_for_target(self, target_host):
        """Find the local network IP that routes to the target iLO host."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            # Connect UDP socket to target host to let OS select outbound interface
            s.connect((target_host, 443))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            pass

        # Fallback to general hostname resolution
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"

    def get_all_local_ips(self):
        """Get list of all local IPv4 addresses on host."""
        ips = []
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
        return ips or ["127.0.0.1"]

    def start_serving(self, file_path, target_host=None, preferred_ip=None):
        with self.lock:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"ISO file not found: {file_path}")

            self.stop_serving()

            self.mounted_file = os.path.abspath(file_path)
            self.mounted_name = os.path.basename(file_path)

            lan_ip = preferred_ip or (self.get_lan_ip_for_target(target_host) if target_host else "127.0.0.1")

            handler_cls = self._create_handler()
            # Try binding to self.port, increment if occupied
            for p in range(self.port, self.port + 20):
                try:
                    self.server = ThreadedVMediaHTTPServer((self.bind_ip, p), handler_cls)
                    self.port = p
                    break
                except OSError:
                    continue

            if not self.server:
                raise RuntimeError("Could not bind HTTP server for Virtual Media on any port.")

            self.active = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()

            safe_name = urllib.parse.quote(self.mounted_name)
            media_url = f"http://{lan_ip}:{self.port}/{safe_name}"
            print(f"[VirtualMediaServer] Serving {self.mounted_file} at {media_url}")
            return {
                "active": True,
                "url": media_url,
                "file_path": self.mounted_file,
                "file_name": self.mounted_name,
                "file_size": os.path.getsize(self.mounted_file),
                "port": self.port,
                "ip": lan_ip
            }

    def stop_serving(self):
        server_to_close = None
        with self.lock:
            if self.server:
                server_to_close = self.server
                self.server = None
            self.active = False
            self.mounted_file = None
            self.mounted_name = None

        if server_to_close:
            try:
                server_to_close.shutdown()
                server_to_close.server_close()
            except Exception as e:
                print(f"[VirtualMediaServer] Error shutting down: {e}")

    def get_status(self):
        with self.lock:
            if not self.active or not self.mounted_file:
                return {"active": False, "url": None, "file_name": None, "file_size": 0}
            return {
                "active": True,
                "file_name": self.mounted_name,
                "file_path": self.mounted_file,
                "file_size": os.path.getsize(self.mounted_file) if os.path.exists(self.mounted_file) else 0,
                "port": self.port
            }

    def _create_handler(self):
        vms = self

        class VMediaHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Quiet logging for bulk transfers
                pass

            def do_HEAD(self):
                self._send_headers(only_headers=True)

            def do_GET(self):
                self._send_headers(only_headers=False)

            def _send_headers(self, only_headers=False):
                if not vms.mounted_file or not os.path.exists(vms.mounted_file):
                    self.send_error(404, "No image mounted")
                    return

                total_size = os.path.getsize(vms.mounted_file)
                range_header = self.headers.get("Range")

                start = 0
                end = total_size - 1

                if range_header:
                    m = re.search(r"bytes=(\d+)-(\d*)", range_header)
                    if m:
                        start = int(m.group(1))
                        if m.group(2):
                            end = int(m.group(2))
                        if start >= total_size or end >= total_size or start > end:
                            self.send_error(416, "Requested Range Not Satisfiable")
                            return

                        self.send_response(206)
                        self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
                    else:
                        self.send_response(200)
                else:
                    self.send_response(200)

                length = end - start + 1
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                if only_headers:
                    return

                try:
                    with open(vms.mounted_file, "rb") as f:
                        f.seek(start)
                        remaining = length
                        chunk_size = 64 * 1024
                        while remaining > 0:
                            read_len = min(remaining, chunk_size)
                            chunk = f.read(read_len)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (ConnectionResetError, BrokenPipeError):
                    pass

        return VMediaHandler

# Global instance
vmedia_server = VirtualMediaServer(port=8088)
