import os
import sys
import re
import json
import time
import mimetypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import urllib.request
import urllib.error

# Ensure backend directory is in sys.path for relative imports
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from server_store import ServerStore
from vmedia_server import vmedia_server
from ssl_proxy import ilo_ssl_proxy
from ilo_client import IloClient, IloCommunicationError
from console_launcher import ConsoleLauncher
from macro_sender import macro_sender

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

server_store = ServerStore()
console_launcher = ConsoleLauncher(ROOT_DIR)

# Active connected client cache
active_lock = threading.Lock()
active_client: IloClient = None
active_server_info = None

# ==================== Log Collector & Interceptor ====================
import datetime

class LogCollector:
    def __init__(self, max_entries=1000):
        self.lock = threading.Lock()
        self.entries = []
        self.max_entries = max_entries
        self.counter = 0

    def add(self, message: str, source="BACKEND", level="INFO"):
        clean_msg = message.strip()
        if not clean_msg:
            return

        if "[TlsBridge]" in clean_msg:
            source = "BRIDGE"
        elif "[ConsoleLauncher]" in clean_msg:
            source = "CONSOLE"
        elif "[API]" in clean_msg:
            source = "API"
        elif "[VMEDIA]" in clean_msg:
            source = "VMEDIA"
        elif "[IloSSLProxy]" in clean_msg:
            source = "PROXY"

        low = clean_msg.lower()
        if "error" in low or "exception" in low or "fail" in low:
            level = "ERROR"
        elif "warn" in low:
            level = "WARN"
        elif "success" in low or "[ok]" in low or "online" in low:
            level = "OK"

        now_str = datetime.datetime.now().strftime("%H:%M:%S")

        with self.lock:
            self.counter += 1
            entry = {
                "id": self.counter,
                "timestamp": now_str,
                "source": source,
                "level": level,
                "message": clean_msg
            }
            self.entries.append(entry)
            if len(self.entries) > self.max_entries:
                self.entries.pop(0)

    def get_logs(self, since_id=0, limit=500):
        with self.lock:
            if since_id > 0:
                filtered = [e for e in self.entries if e["id"] > since_id]
            else:
                filtered = self.entries[-limit:]
            return list(filtered)

    def clear(self):
        with self.lock:
            self.entries.clear()

log_collector = LogCollector()

class OutputInterceptor:
    def __init__(self, original_stream, default_source="BACKEND", default_level="INFO"):
        self.original_stream = original_stream
        self.default_source = default_source
        self.default_level = default_level

    def write(self, text):
        if text:
            for line in text.splitlines():
                if line.strip():
                    log_collector.add(line, source=self.default_source, level=self.default_level)
        return self.original_stream.write(text)

    def flush(self):
        return self.original_stream.flush()

sys.stdout = OutputInterceptor(sys.__stdout__, default_source="BACKEND", default_level="INFO")
sys.stderr = OutputInterceptor(sys.__stderr__, default_source="BACKEND", default_level="ERROR")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Suppress socket disconnection errors when client browser closes tabs or navigates
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)

class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging - exclude high-frequency polling
        if "/api/" in self.path and not self.path.startswith("/api/logs") and not self.path.startswith("/api/status"):
            msg = f"[API] {self.command} {self.path} - {args[1] if len(args) > 1 else ''}"
            print(msg)

    def send_json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:
            pass

    def read_json_body(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            raw = self.rfile.read(content_len).decode("utf-8")
            return json.loads(raw)
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()

    def proxy_to_ilo(self, path: str, query: str, method: str):
        global active_client
        with active_lock:
            if active_client:
                ilo_ssl_proxy.set_target(active_client.host, active_client.port)

        if ilo_ssl_proxy.target_host in ("127.0.0.1", "") and not active_client:
            err_msg = "Not connected to an iLO server. Please connect on the Overview dashboard first.".encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)
            return

        if not ilo_ssl_proxy.active:
            try:
                ilo_ssl_proxy.start()
            except Exception:
                pass

        # Strip /ilo-web prefix if present
        if path.startswith("/ilo-web"):
            target_path = path[len("/ilo-web"):]
            if not target_path or target_path == "":
                target_path = "/"
        else:
            target_path = path

        if query:
            target_path += f"?{query}"

        target_url = f"{ilo_ssl_proxy.get_url()}{target_path}"

        try:
            req = urllib.request.Request(target_url, method=method)

            # Forward request headers
            for header, value in self.headers.items():
                if header.lower() not in ("host", "content-length", "transfer-encoding"):
                    req.add_header(header, value)

            # Forward body for POST/PUT
            body_data = None
            if method in ("POST", "PUT"):
                content_len = int(self.headers.get("Content-Length", 0))
                if content_len > 0:
                    body_data = self.rfile.read(content_len)

            opener = urllib.request.build_opener()
            try:
                resp = opener.open(req, data=body_data, timeout=20)
                resp_code = resp.status
                resp_headers = resp.headers
                resp_data = resp.read()
            except urllib.error.HTTPError as e:
                resp_code = e.code
                resp_headers = e.headers
                resp_data = e.read()

            self.send_response(resp_code)
            for h, val in resp_headers.items():
                if h.lower() not in ("transfer-encoding", "content-length", "x-frame-options", "content-security-policy", "cross-origin-opener-policy", "cross-origin-embedder-policy"):
                    if h.lower() == "set-cookie":
                        val = re.sub(r"(?i);\s*Secure", "", val)
                        val = re.sub(r"(?i);\s*SameSite=[^;]+", "", val)
                        val = re.sub(r"(?i);\s*Domain=[^;]+", "", val)
                    self.send_header(h, val)

            self.send_header("Content-Length", str(len(resp_data)))
            self.end_headers()
            self.wfile.write(resp_data)
        except Exception as e:
            err_msg = f"iLO Web Proxy Error: {str(e)}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_get(path, parsed.query)
        elif (path.startswith("/ilo-web") or 
              path.startswith("/json/") or 
              path.startswith("/html/") or 
              path.startswith("/js/") or 
              path.startswith("/css/") or 
              path.startswith("/images/") or 
              path.startswith("/favicon.ico")):
            self.proxy_to_ilo(path, parsed.query, "GET")
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_post(path)
        elif (path.startswith("/ilo-web") or 
              path.startswith("/json/") or 
              path.startswith("/html/") or 
              path.startswith("/js/") or 
              path.startswith("/css/") or 
              path.startswith("/images/")):
            self.proxy_to_ilo(path, parsed.query, "POST")
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/servers/"):
            server_id = path[len("/api/servers/"):]
            res = server_store.delete(server_id)
            self.send_json({"success": res, "deleted_id": server_id})
        elif path == "/api/logs":
            log_collector.clear()
            self.send_json({"success": True})
        else:
            self.send_error(404)

    # ==================== API Route Handlers ====================

    def handle_api_get(self, path: str, query: str):
        global active_client, active_server_info

        if path == "/api/servers":
            servers = server_store.get_all()
            # Do not leak plaintext passwords in list if unnecessary
            clean_servers = []
            for s in servers:
                copy_s = dict(s)
                copy_s["has_password"] = bool(copy_s.get("password"))
                clean_servers.append(copy_s)
            self.send_json({"servers": clean_servers})

        elif path == "/api/status":
            with active_lock:
                if not active_client or not active_server_info:
                    self.send_json({"connected": False})
                    return

                try:
                    stat = active_client.get_host_status()
                    active_server_info["power_status"] = stat["power_status"]
                    active_server_info["uid_status"] = stat["uid_status"]
                    pwr_read = stat.get("power_reading", "0 Watts")
                    active_server_info["power_reading"] = pwr_read
                    if "hardware" in active_server_info and isinstance(active_server_info["hardware"], dict):
                        if "power" not in active_server_info["hardware"]:
                            active_server_info["hardware"]["power"] = {}
                        active_server_info["hardware"]["power"]["present_reading"] = pwr_read
                except Exception as e:
                    print(f"[API] Error updating live power/uid: {e}")

                if not active_server_info.get("hardware"):
                    try:
                        hw_xml = active_client.send_ribcl('<SERVER_INFO MODE="read"><GET_EMBEDDED_HEALTH/></SERVER_INFO>')
                        active_server_info["hardware"] = active_client.parse_embedded_health(hw_xml)
                    except Exception:
                        pass

                vmedia_stat = vmedia_server.get_status()
                proxy_url = ilo_ssl_proxy.get_url() if ilo_ssl_proxy.active else None

                self.send_json({
                    "connected": True,
                    "server": active_server_info,
                    "vmedia": vmedia_stat,
                    "proxy_url": proxy_url
                })

        elif path == "/api/hardware":
            with active_lock:
                if not active_client or not active_server_info:
                    self.send_json({"error": "Not connected to an iLO server"}, 400)
                    return
                client = active_client
            try:
                hw_xml = client.send_ribcl('<SERVER_INFO MODE="read"><GET_EMBEDDED_HEALTH/></SERVER_INFO>')
                hw_info = client.parse_embedded_health(hw_xml)
                with active_lock:
                    if active_server_info:
                        active_server_info["hardware"] = hw_info
                self.send_json({"success": True, "hardware": hw_info})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/boot":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "Not connected to an iLO server"}, 400)
                    return
                try:
                    onetime = active_client.get_one_time_boot()
                    persistent = active_client.get_persistent_boot()
                    self.send_json({
                        "success": True,
                        "onetime_boot": onetime,
                        "persistent_boot": persistent
                    })
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/vmedia":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "Not connected to an iLO server"}, 400)
                    return
                try:
                    ilo_vm = active_client.get_vm_status("CDROM")
                    local_vm = vmedia_server.get_status()
                    self.send_json({
                        "success": True,
                        "ilo_vmedia": ilo_vm,
                        "local_vmedia": local_vm
                    })
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/network-ips":
            with active_lock:
                target_host = active_client.host if active_client else None
            best_ip = vmedia_server.get_lan_ip_for_target(target_host) if target_host else "127.0.0.1"
            all_ips = vmedia_server.get_all_local_ips()
            self.send_json({"best_ip": best_ip, "all_ips": all_ips})

        elif path == "/api/hplocons-status":
            hplocons_path = console_launcher.find_hplocons()
            with active_lock:
                target_host = active_client.host if active_client else None
                target_port = active_client.port if active_client else 443
            self.send_json({
                "installed": bool(hplocons_path),
                "path": hplocons_path,
                "bridge_host": "127.0.0.1",
                "bridge_port": ilo_ssl_proxy.listen_port,
                "bridge_url": ilo_ssl_proxy.get_url(),
                "bridge_https_port": ilo_ssl_proxy.https_port,
                "bridge_https_url": ilo_ssl_proxy.get_https_url(),
                "bridge_https_target": ilo_ssl_proxy.get_https_target(),
                "target_host": target_host,
                "target_port": target_port
            })

        elif path == "/api/logs":
            query_params = urllib.parse.parse_qs(query)
            since_id = int(query_params.get("since", [0])[0])
            limit = int(query_params.get("limit", [500])[0])
            logs = log_collector.get_logs(since_id=since_id, limit=limit)
            self.send_json({"logs": logs, "count": len(logs)})

        else:
            self.send_error(404, "API endpoint not found")

    def handle_api_post(self, path: str):
        global active_client, active_server_info
        body = self.read_json_body()

        if path == "/api/connect":
            host = body.get("host", "").strip()
            user = body.get("user", "").strip()
            password = body.get("password", "").strip()
            port = int(body.get("port", 443))

            if not host or not user:
                self.send_json({"success": False, "error": "Host and username required"}, 400)
                return

            try:
                # 1. Configure and start Java TLS Bridge for this host
                ilo_ssl_proxy.set_target(host, port)
                ilo_ssl_proxy.start()

                # 2. Connect through bridge to support 3DES, RC4, and legacy TLS
                client = IloClient(host=host, user=user, password=password, port=port, bridge_url=ilo_ssl_proxy.get_url())
                info = client.test_connection()

                with active_lock:
                    active_client = client
                    active_server_info = info

                self.send_json({
                    "success": True,
                    "server": info,
                    "proxy_url": ilo_ssl_proxy.get_url()
                })
            except Exception as e:
                self.send_json({"success": False, "error": f"Connection error: {str(e)}"}, 500)

        elif path == "/api/disconnect":
            with active_lock:
                active_client = None
                active_server_info = None
            vmedia_server.stop_serving()
            ilo_ssl_proxy.stop()
            self.send_json({"success": True})

        elif path == "/api/servers":
            server_data = server_store.add_or_update(body)
            self.send_json({"success": True, "server": server_data})

        elif path == "/api/power":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            action = body.get("action", "momentary")
            try:
                res = client.set_power(action)
                with active_lock:
                    if active_server_info and "power_status" in res:
                        active_server_info["power_status"] = res["power_status"]
                self.send_json(res)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/uid":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            enable = bool(body.get("enable", True))
            try:
                res = client.set_uid(enable)
                with active_lock:
                    if active_server_info:
                        active_server_info["uid_status"] = "ON" if enable else "OFF"
                self.send_json({"success": res, "uid_status": "ON" if enable else "OFF"})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/boot/onetime":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            device = body.get("device", "NORMAL")
            try:
                res = client.set_one_time_boot(device)
                self.send_json(res)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/boot/persistent":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            devices = body.get("devices", [])
            try:
                res = client.set_persistent_boot(devices)
                self.send_json(res)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/vmedia/mount":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            file_path = body.get("file_path", "").strip()
            boot_option = body.get("boot_option", "BOOT_ONCE")
            preferred_ip = body.get("preferred_ip")

            if not file_path:
                self.send_json({"success": False, "error": "ISO file path required"}, 400)
                return

            try:
                # 1. Start local streaming server
                vmedia_info = vmedia_server.start_serving(
                    file_path=file_path,
                    target_host=client.host,
                    preferred_ip=preferred_ip
                )

                # 2. Tell iLO to mount the HTTP URL
                res = client.insert_virtual_media(
                    image_url=vmedia_info["url"],
                    device="CDROM",
                    boot_option=boot_option
                )

                self.send_json({
                    "success": res.get("success", True),
                    "vmedia": vmedia_info,
                    "ilo_response": res
                })
            except Exception as e:
                vmedia_server.stop_serving()
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/vmedia/eject":
            with active_lock:
                if not active_client:
                    self.send_json({"error": "No active connection"}, 400)
                    return
                client = active_client

            try:
                res = client.eject_virtual_media("CDROM")
                vmedia_server.stop_serving()
                self.send_json({"success": True, "ilo_response": res})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/macro/send":
            macro = body.get("macro", "").strip()
            if not macro:
                self.send_json({"success": False, "error": "Macro name required"}, 400)
                return
            with active_lock:
                client = active_client
            res = macro_sender.dispatch_macro(macro, client)
            self.send_json(res)

        elif path == "/api/console/launch":
            with active_lock:
                client = active_client

            if not client:
                # Fallback to credentials in request body or saved server profile
                req_host = body.get("host")
                req_user = body.get("user")
                req_pass = body.get("password")
                req_port = int(body.get("port", 443))

                if not req_host or not req_user:
                    saved = server_store.get_all()
                    if saved:
                        s = saved[0]
                        req_host = req_host or s.get("host")
                        req_user = req_user or s.get("user")
                        req_pass = req_pass or s.get("password")
                        req_port = req_port or int(s.get("port", 443))

                if not req_host or not req_user:
                    self.send_json({"error": "No active connection and no server credentials available"}, 400)
                    return

                ilo_ssl_proxy.set_target(req_host, req_port)
                ilo_ssl_proxy.start()
                client = IloClient(host=req_host, user=req_user, password=req_pass, port=req_port, bridge_url=ilo_ssl_proxy.get_url())

            console_type = body.get("type", "java")
            try:
                if console_type == "java":
                    if not client.session_key:
                        try:
                            client.login_json()
                        except Exception:
                            pass
                    res = console_launcher.launch_java_console(
                        host=client.host,
                        user=client.user,
                        password=client.password,
                        session_key=client.session_key
                    )
                    self.send_json(res)
                elif console_type == "hplocons":
                    use_bridge = body.get("use_bridge", True)
                    if use_bridge:
                        ilo_ssl_proxy.set_target(client.host, client.port)
                        ilo_ssl_proxy.start()
                        target_h = "127.0.0.1"
                        target_p = ilo_ssl_proxy.https_port
                    else:
                        target_h = client.host
                        target_p = client.port
                    res = console_launcher.launch_hplocons(
                        host=target_h,
                        user=client.user,
                        password=client.password,
                        port=target_p
                    )
                    self.send_json(res)
                elif console_type == "html5":
                    url = console_launcher.get_html5_url(client.host, client.port)
                    self.send_json({"success": True, "type": "html5", "url": url})
                else:
                    self.send_json({"error": f"Unknown console type: {console_type}"}, 400)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/shutdown":
            self.send_json({"success": True, "message": "All services shutting down"})
            def _kill_everything():
                time.sleep(0.1)
                cleanup_all()
                os._exit(0)
            threading.Thread(target=_kill_everything, daemon=True).start()

        elif path == "/api/open-external":
            url = body.get("url", "http://127.0.0.1:8089")
            try:
                try:
                    os.startfile(url)
                except Exception:
                    import webbrowser
                    webbrowser.open(url)
                self.send_json({"success": True, "url": url})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        else:
            self.send_error(404, "API endpoint not found")

    # ==================== Static Frontend Serving ====================

    def serve_static(self, path: str):
        if path in ("", "/"):
            path = "/index.html"

        safe_path = os.path.normpath(path.lstrip("/\\"))
        file_path = os.path.join(FRONTEND_DIR, safe_path)

        if not os.path.isfile(file_path):
            # Fallback to index.html for SPA routing
            file_path = os.path.join(FRONTEND_DIR, "index.html")

        if not os.path.isfile(file_path):
            self.send_error(404, "Frontend file not found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        if file_path.endswith(".css"):
            mime_type = "text/css; charset=utf-8"
        elif file_path.endswith(".js"):
            mime_type = "application/javascript; charset=utf-8"
        elif file_path.endswith(".html"):
            mime_type = "text/html; charset=utf-8"

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

import atexit
import signal

def cleanup_all():
    global active_client, active_server_info
    with active_lock:
        active_client = None
        active_server_info = None
    try:
        vmedia_server.stop_serving()
    except Exception:
        pass
    try:
        ilo_ssl_proxy.stop()
    except Exception:
        pass
    try:
        console_launcher.kill_all()
    except Exception:
        pass

atexit.register(cleanup_all)

def _sig_handler(sig, frame):
    cleanup_all()
    os._exit(0)

try:
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _sig_handler)
except Exception:
    pass

def run_server(port=5050):
    server = ThreadedHTTPServer(("127.0.0.1", port), ApiHandler)
    print(f"============================================================")
    print(f"  iLO Suite started")
    print(f"  Web UI: http://127.0.0.1:{port}")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        cleanup_all()
        server.server_close()

if __name__ == "__main__":
    p = 5050
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        p = int(sys.argv[1])
    run_server(p)
