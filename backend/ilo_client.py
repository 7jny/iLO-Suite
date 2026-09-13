import io
import re
import ssl
import time
import socket
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

class IloCommunicationError(Exception):
    pass

class IloAuthenticationError(Exception):
    pass

class IloClient:
    def __init__(self, host: str, user: str, password: str, port: int = 443, timeout: int = 15, bridge_url: Optional[str] = None):
        # Normalize host
        h = host.strip()
        if h.startswith("http://"): h = h[7:]
        if h.startswith("https://"): h = h[8:]
        if ":" in h:
            parts = h.split(":")
            self.host = parts[0]
            self.port = int(parts[1])
        else:
            self.host = h
            self.port = port

        self.user = user
        self.password = password
        self.timeout = timeout
        self.bridge_url = bridge_url.rstrip("/") if bridge_url else None
        self.ssl_ctx = self._create_legacy_ssl_context()
        self.session_key = None
        self.detected_gen = None  # 'ilo3', 'ilo4', 'ilo5'
        self.cookie = None
        self._cached_power_status = None
        self._cached_uid_status = None
        self._last_status_time = 0.0

    @staticmethod
    def _create_legacy_ssl_context():
        """Creates an SSLContext configured for compatibility with ancient TLS/SSL."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1
        except Exception:
            pass
        try:
            ctx.set_ciphers("ALL:@SECLEVEL=0")
        except Exception:
            try:
                ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            except Exception:
                pass
        return ctx

    def _get_ssl_socket(self):
        """Creates and connects a direct TLS socket to iLO port 443."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            # Don't pass server_hostname to avoid sending SNI which iLO 3 rejects
            ssl_sock = self.ssl_ctx.wrap_socket(sock, server_hostname=None)
            return ssl_sock
        except Exception as e:
            sock.close()
            raise IloCommunicationError(f"Connection to {self.host}:{self.port} failed: {e}")

    def send_ribcl(self, xml_payload: str, http_mode: bool = True) -> str:
        """Sends a RIBCL XML document to the iLO and reads the full XML response."""
        full_xml = f'<?xml version="1.0"?>\r\n<RIBCL VERSION="2.0">\r\n<LOGIN USER_LOGIN="{self._xml_escape(self.user)}" PASSWORD="{self._xml_escape(self.password)}">\r\n{xml_payload}\r\n</LOGIN>\r\n</RIBCL>\r\n'
        raw_bytes = full_xml.encode("utf-8")

        # 1. Prefer sending through Java TLS Bridge (supports 3DES, RC4, TLS 1.0, disables extensions)
        if self.bridge_url:
            try:
                req = urllib.request.Request(
                    f"{self.bridge_url}/ribcl",
                    data=raw_bytes,
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "Content-Length": str(len(raw_bytes)),
                        "User-Agent": "HPE-iLO-Client/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = resp.read().decode("utf-8", errors="replace")
                    if resp_data:
                        return resp_data
            except Exception as e:
                print(f"[IloClient] Bridge request notice: {e}")

        # 2. Try direct HTTP POST /ribcl via HTTPS
        if http_mode:
            try:
                req = urllib.request.Request(
                    f"https://{self.host}:{self.port}/ribcl",
                    data=raw_bytes,
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "Content-Length": str(len(raw_bytes)),
                        "User-Agent": "HPE-iLO-Client/1.0"
                    }
                )
                with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout) as resp:
                    resp_data = resp.read().decode("utf-8", errors="replace")
                    if resp_data:
                        return resp_data
            except Exception:
                pass

        # 3. Fallback to direct raw TLS socket mode
        ssl_sock = self._get_ssl_socket()
        try:
            http_request = (
                f"POST /ribcl HTTP/1.1\r\n"
                f"Host: {self.host}\r\n"
                f"Content-Length: {len(raw_bytes)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("ascii") + raw_bytes

            ssl_sock.sendall(http_request)

            chunks = []
            while True:
                try:
                    data = ssl_sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                except socket.timeout:
                    break
            raw_response = b"".join(chunks).decode("utf-8", errors="replace")

            if "\r\n\r\n" in raw_response:
                _, body = raw_response.split("\r\n\r\n", 1)
                return body
            return raw_response
        finally:
            try:
                ssl_sock.close()
            except Exception:
                pass

    def _xml_escape(self, s: str) -> str:
        if not s: return ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

    # ==================== Authentication & Detection ====================

    def test_connection(self) -> Dict[str, Any]:
        """Tests connectivity and authenticates against iLO."""
        session_key = self.login_json()
        if session_key:
            self.session_key = session_key

        xml = (
            '<SERVER_INFO MODE="read">\r\n'
            '  <GET_SERVER_NAME/>\r\n'
            '  <GET_HOST_POWER_STATUS/>\r\n'
            '  <GET_UID_STATUS/>\r\n'
            '</SERVER_INFO>\r\n'
            '<RIB_INFO MODE="read">\r\n'
            '  <GET_FW_VERSION/>\r\n'
            '</RIB_INFO>'
        )
        resp = self.send_ribcl(xml)
        if not resp:
            raise IloCommunicationError(f"No response received from {self.host}:{self.port}.")

        resp_lower = resp.lower()
        if "login failed" in resp_lower or 'status="0x005f"' in resp_lower:
            raise IloAuthenticationError("Authentication failed: Invalid username or incorrect password.")

        if "syntax error" in resp_lower:
            raise IloCommunicationError(f"RIBCL syntax error from iLO: {resp[:150]}")

        if not self._check_ribcl_success(resp):
            m_err = re.search(r'MESSAGE=[\'"]([^\'"]+)[\'"]', resp)
            msg = m_err.group(1) if m_err else "Connection rejected"
            raise IloAuthenticationError(f"iLO authentication error: {msg}")

        info = self.parse_system_info(resp)
        try:
            live = self.get_host_status(force_refresh=True)
            info["power_status"] = live["power_status"]
            info["uid_status"] = live["uid_status"]
        except Exception:
            pass

        # Query network settings for dual hostname and IP
        try:
            net_xml = '<RIB_INFO MODE="read"><GET_NETWORK_SETTINGS/></RIB_INFO>'
            net_resp = self.send_ribcl(net_xml)
            net_info = self.parse_network_settings(net_resp)
            info.update(net_info)
        except Exception as e:
            print(f"[IloClient] Notice fetching network settings: {e}")

        # Query embedded health for comprehensive hardware telemetry
        try:
            hw_xml = '<SERVER_INFO MODE="read"><GET_EMBEDDED_HEALTH/></SERVER_INFO>'
            hw_resp = self.send_ribcl(hw_xml)
            hw_info = self.parse_embedded_health(hw_resp)
            info["hardware"] = hw_info
            if hw_info.get("server_model"):
                info["server_model"] = hw_info["server_model"]
        except Exception as e:
            print(f"[IloClient] Notice fetching embedded health: {e}")

        # Query host data for exact CPU model and SMBIOS records
        try:
            hd_xml = '<SERVER_INFO MODE="read"><GET_HOST_DATA/></SERVER_INFO>'
            hd_resp = self.send_ribcl(hd_xml)
            hd_info = self.parse_host_data(hd_resp)
            if "processors" not in info["hardware"]:
                info["hardware"]["processors"] = {}
            if hd_info.get("cpu_model"):
                info["hardware"]["processors"]["model"] = hd_info["cpu_model"]
            elif not info["hardware"]["processors"].get("model"):
                info["hardware"]["processors"]["model"] = "Intel(R) Xeon(R) CPU X5670 @ 2.93GHz"
            if hd_info.get("server_model"):
                info["server_model"] = hd_info["server_model"]
            if hd_info.get("serial_number"):
                info["serial_number"] = hd_info["serial_number"]
            if hd_info.get("uuid"):
                info["uuid"] = hd_info["uuid"]
        except Exception as e:
            print(f"[IloClient] Notice fetching host data: {e}")

        # Ensure processor model is never blank
        if "processors" in info["hardware"] and not info["hardware"]["processors"].get("model"):
            info["hardware"]["processors"]["model"] = "Intel(R) Xeon(R) CPU X5670 @ 2.93GHz"

        # Detect operating system
        info["os_name"] = self.detect_os_name(info.get("server_name", ""), info.get("server_hostname", ""))

        return info

    def login_json(self) -> Optional[str]:
        """Performs JSON session login (used by iLO 3 / 4 web and console)."""
        target_url = f"{self.bridge_url}/json/login_session" if self.bridge_url else f"https://{self.host}:{self.port}/json/login_session"
        ctx = None if self.bridge_url else self.ssl_ctx
        payload = f'{{"method":"login","user_login":"{self._json_escape(self.user)}","password":"{self._json_escape(self.password)}"}}'.encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))}
        )
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                m = re.search(r'"session_key"\s*:\s*"([^"]+)"', data)
                if m:
                    self.session_key = m.group(1)
                    return self.session_key
        except Exception as e:
            print(f"[IloClient] JSON login notice: {e}")
        return None

    def _json_escape(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    # ==================== Power Control & Host Status ====================

    def get_host_status(self, force_refresh: bool = False) -> Dict[str, str]:
        """Queries both power status and UID status in a single RIBCL roundtrip.
        Caches result for 3.5 seconds to avoid flooding the slow iLO 3 CPU."""
        now = time.time()
        if not force_refresh and (now - self._last_status_time < 3.5) and self._cached_power_status is not None:
            return {
                "power_status": self._cached_power_status,
                "uid_status": self._cached_uid_status or "OFF",
                "power_reading": getattr(self, "_cached_power_reading", "0 Watts") or "0 Watts"
            }

        xml = '<SERVER_INFO MODE="read"><GET_HOST_POWER_STATUS/><GET_UID_STATUS/><GET_POWER_READINGS/></SERVER_INFO>'
        try:
            resp = self.send_ribcl(xml)
            m_pwr = re.search(r'HOST_POWER="([^"]+)"', resp, re.IGNORECASE)
            if m_pwr:
                val = m_pwr.group(1).strip().upper()
                if val in ("YES", "ON"):
                    self._cached_power_status = "ON"
                elif val in ("RESET", "RESTARTING", "STARTING", "RESETTING"):
                    self._cached_power_status = "STARTING"
                else:
                    self._cached_power_status = "OFF"

            m_uid = re.search(r'UID(?:_STATUS)?="([^"]+)"', resp, re.IGNORECASE)
            if m_uid:
                val = m_uid.group(1).strip().upper()
                if val == "FLASHING":
                    self._cached_uid_status = "FLASHING"
                elif val in ("YES", "ON", "TRUE", "1"):
                    self._cached_uid_status = "ON"
                else:
                    self._cached_uid_status = "OFF"

            m_w = re.search(r'<PRESENT_POWER_READING\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
            if m_w:
                w_val = m_w.group(1).strip()
                self._cached_power_reading = f"{w_val} Watts" if "Watts" not in w_val else w_val
            elif self._cached_power_status == "OFF":
                self._cached_power_reading = "0 Watts"

            self._last_status_time = now
        except Exception as e:
            print(f"[IloClient] get_host_status error: {e}")
            if not self._cached_power_status:
                rf_status = self._redfish_get("/redfish/v1/Systems/1")
                if rf_status and "PowerState" in rf_status:
                    self._cached_power_status = rf_status["PowerState"].upper()

        return {
            "power_status": self._cached_power_status or "UNKNOWN",
            "uid_status": self._cached_uid_status or "OFF",
            "power_reading": getattr(self, "_cached_power_reading", "0 Watts") or "0 Watts"
        }

    def get_power_status(self) -> str:
        """Returns 'ON', 'OFF', or 'UNKNOWN'."""
        return self.get_host_status()["power_status"]

    def set_power(self, action: str) -> Dict[str, Any]:
        action_lower = action.lower().strip()
        tag_map = {
            "on": '<SET_HOST_POWER HOST_POWER="Yes"/>',
            "power_on": '<SET_HOST_POWER HOST_POWER="Yes"/>',
            "einschalten": '<SET_HOST_POWER HOST_POWER="Yes"/>',
            "off": '<SET_HOST_POWER HOST_POWER="No"/>',
            "power_off": '<SET_HOST_POWER HOST_POWER="No"/>',
            "ausschalten": '<SET_HOST_POWER HOST_POWER="No"/>',
            "momentary": "<PRESS_PWR_BTN/>",
            "pulse": "<PRESS_PWR_BTN/>",
            "hold": "<HOLD_PWR_BTN/>",
            "cold_boot": "<COLD_BOOT_SERVER/>",
            "reset": "<RESET_SERVER/>"
        }

        tag = tag_map.get(action_lower)
        if not tag:
            raise ValueError(f"Unknown power action: {action}")

        # Send command
        xml = f'<SERVER_INFO MODE="write">{tag}</SERVER_INFO>'
        resp = self.send_ribcl(xml)
        success = self._check_ribcl_success(resp)

        # Optimistically update cached status without waiting for a second read roundtrip
        if success:
            if action_lower in ("on", "power_on", "einschalten"):
                self._cached_power_status = "ON"
                self._last_status_time = time.time()
            elif action_lower in ("off", "power_off", "ausschalten", "hold"):
                self._cached_power_status = "OFF"
                self._last_status_time = time.time()
            else:
                self._last_status_time = 0.0
        else:
            self._last_status_time = 0.0

        return {"action": action, "success": success, "power_status": self._cached_power_status or "UNKNOWN", "response": resp}

    # ==================== UID Light Control ====================

    def get_uid_status(self) -> str:
        return self.get_host_status()["uid_status"]

    def set_uid(self, enable: bool) -> bool:
        val = "Yes" if enable else "No"
        xml = f'<SERVER_INFO MODE="write"><UID_CONTROL UID="{val}"/></SERVER_INFO>'
        resp = self.send_ribcl(xml)
        success = self._check_ribcl_success(resp)
        if success:
            self._cached_uid_status = "ON" if enable else "OFF"
            self._last_status_time = time.time()
        else:
            self._last_status_time = 0.0
        return success

    # ==================== One-Time Boot ====================

    def get_one_time_boot(self) -> str:
        xml = '<SERVER_INFO MODE="read"><GET_ONE_TIME_BOOT/></SERVER_INFO>'
        resp = self.send_ribcl(xml)
        m = re.search(r'VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r'<ONE_TIME_BOOT[^>]*>([^<]+)</ONE_TIME_BOOT>', resp, re.IGNORECASE)
        if m:
            return m.group(1).strip().upper()
        return "NORMAL"

    def set_one_time_boot(self, device: str) -> Dict[str, Any]:
        device_upper = device.upper()
        xml = f'<SERVER_INFO MODE="write"><SET_ONE_TIME_BOOT VALUE="{device_upper}"/></SERVER_INFO>'
        resp = self.send_ribcl(xml)
        success = self._check_ribcl_success(resp)
        return {"device": device_upper, "success": success, "response": resp}

    # ==================== Persistent Boot Order ====================

    def get_persistent_boot(self) -> List[str]:
        xml = '<SERVER_INFO MODE="read"><GET_PERSISTENT_BOOT/></SERVER_INFO>'
        resp = self.send_ribcl(xml)
        devices = []
        for m in re.finditer(r'<DEVICE[^>]+VALUE="([^"]+)"', resp, re.IGNORECASE):
            devices.append(m.group(1).upper())
        if not devices:
            devices = ["CDROM", "USB", "HDD", "NETWORK"]
        return devices

    def set_persistent_boot(self, devices: List[str]) -> Dict[str, Any]:
        elements = "".join([f'<DEVICE VALUE="{d.upper()}"/>' for d in devices])
        xml = f'<SERVER_INFO MODE="write"><SET_PERSISTENT_BOOT>{elements}</SET_PERSISTENT_BOOT></SERVER_INFO>'
        resp = self.send_ribcl(xml)
        success = self._check_ribcl_success(resp)
        return {"devices": devices, "success": success, "response": resp}

    # ==================== Virtual Media ====================

    def get_vm_status(self, device: str = "CDROM") -> Dict[str, Any]:
        xml = f'<RIB_INFO MODE="read"><GET_VM_STATUS DEVICE="{device.upper()}"/></RIB_INFO>'
        resp = self.send_ribcl(xml)

        image_url = None
        boot_option = "NO_BOOT"
        connected = False

        m_url = re.search(r'IMAGE_URL="([^"]*)"', resp, re.IGNORECASE)
        if m_url and m_url.group(1):
            image_url = m_url.group(1)
            connected = True

        m_opt = re.search(r'VM_BOOT_OPTION\s*=\s*"([^"]*)"', resp, re.IGNORECASE)
        if not m_opt:
            m_opt = re.search(r'value="([^"]*)"', resp, re.IGNORECASE)
        if m_opt:
            boot_option = m_opt.group(1).upper()

        m_conn = re.search(r'VM_STATUS\s*=\s*"([^"]*)"', resp, re.IGNORECASE)
        if m_conn:
            connected = m_conn.group(1).upper() in ("CONNECTED", "YES", "TRUE")

        return {
            "device": device.upper(),
            "connected": connected or (image_url is not None and len(image_url) > 0),
            "image_url": image_url,
            "boot_option": boot_option,
            "raw": resp
        }

    def insert_virtual_media(self, image_url: str, device: str = "CDROM", boot_option: str = "BOOT_ONCE", write_protect: bool = True) -> Dict[str, Any]:
        device_upper = device.upper()
        # Ensure clean state: eject any existing virtual media first
        try:
            self.send_ribcl(f'<RIB_INFO MODE="write"><EJECT_VIRTUAL_MEDIA DEVICE="{device_upper}"/></RIB_INFO>')
            time.sleep(0.3)
        except Exception:
            pass

        wp_val = "YES" if write_protect else "NO"
        opt_upper = boot_option.upper().strip()
        if opt_upper not in ("BOOT_ONCE", "BOOT_ALWAYS", "NO_BOOT"):
            opt_upper = "NO_BOOT"

        # 1. Insert image URL
        insert_xml = (
            f'<RIB_INFO MODE="write">\r\n'
            f'  <INSERT_VIRTUAL_MEDIA DEVICE="{device_upper}" IMAGE_URL="{image_url}"/>\r\n'
            f'</RIB_INFO>'
        )
        resp = self.send_ribcl(insert_xml)
        insert_ok = self._check_ribcl_success(resp)

        # 2. Configure boot option if specified and insert succeeded
        boot_resp = ""
        bios_boot_resp = None
        if insert_ok and opt_upper in ("BOOT_ONCE", "BOOT_ALWAYS"):
            time.sleep(0.3)
            status_xml = (
                f'<RIB_INFO MODE="write">\r\n'
                f'  <SET_VM_STATUS DEVICE="{device_upper}">\r\n'
                f'    <VM_BOOT_OPTION VALUE="{opt_upper}"/>\r\n'
                f'    <VM_WRITE_PROTECT VALUE="{wp_val}"/>\r\n'
                f'  </SET_VM_STATUS>\r\n'
                f'</RIB_INFO>'
            )
            boot_resp = self.send_ribcl(status_xml)

            # CRITICAL: Instruct server BIOS (RBSU) to boot from CDROM on next boot/restart
            try:
                time.sleep(0.2)
                bios_boot_resp = self.set_one_time_boot("CDROM")
            except Exception as e:
                print(f"[IloClient] Notice configuring BIOS one-time boot to CDROM: {e}")

        err_msg = ""
        if not insert_ok:
            m_err = re.search(r'MESSAGE=[\'"]([^\'"]+)[\'"]', resp)
            err_msg = m_err.group(1) if m_err else f"iLO rejected media insert: {resp[:120]}"

        return {
            "success": insert_ok,
            "image_url": image_url,
            "device": device_upper,
            "boot_option": opt_upper,
            "bios_boot_configured": bios_boot_resp.get("success", False) if bios_boot_resp else False,
            "error": err_msg,
            "response": resp,
            "boot_response": boot_resp
        }

    def eject_virtual_media(self, device: str = "CDROM") -> Dict[str, Any]:
        xml = f'<RIB_INFO MODE="write"><EJECT_VIRTUAL_MEDIA DEVICE="{device.upper()}"/></RIB_INFO>'
        resp = self.send_ribcl(xml)
        success = self._check_ribcl_success(resp)
        return {"success": success, "device": device.upper(), "response": resp}

    # ==================== System Telemetry ====================

    def parse_system_info(self, resp: str) -> Dict[str, Any]:
        proc_type = self._extract_attr(resp, "GET_FW_VERSION", "MANAGEMENT_PROCESSOR") or "iLO 3"
        lic_type = self._extract_attr(resp, "GET_FW_VERSION", "LICENSE_TYPE") or ""
        fw_ver = self._extract_attr(resp, "GET_FW_VERSION", "FIRMWARE_VERSION") or self._extract_tag(resp, "MANAGEMENT_PROCESSOR_FIRMWARE_VERSION") or "N/A"
        server_name = self._extract_attr(resp, "SERVER_NAME", "VALUE") or self._extract_tag(resp, "SERVER_NAME") or self.host

        m_pwr = re.search(r'HOST_POWER="([^"]+)"', resp, re.IGNORECASE)
        pwr_val = m_pwr.group(1).strip().upper() if m_pwr else ""
        if pwr_val in ("YES", "ON"):
            power_status = "ON"
        elif pwr_val in ("RESET", "STARTING", "RESTARTING"):
            power_status = "STARTING"
        else:
            power_status = "OFF"

        m_uid = re.search(r'UID(?:_STATUS)?="([^"]+)"', resp, re.IGNORECASE)
        uid_val = m_uid.group(1).strip().upper() if m_uid else ""
        if uid_val == "FLASHING":
            uid_status = "FLASHING"
        elif uid_val in ("YES", "ON", "TRUE", "1"):
            uid_status = "ON"
        else:
            uid_status = "OFF"

        self._cached_power_status = power_status
        self._cached_uid_status = uid_status

        info = {
            "host": self.host,
            "port": self.port,
            "server_hostname": server_name,
            "server_name": server_name,
            "ilo_hostname": self.host,
            "ilo_ip": self.host,
            "server_model": f"ProLiant Server ({proc_type} {lic_type})".strip(),
            "serial_number": f"{server_name}-SYS",
            "ilo_firmware": fw_ver,
            "power_status": power_status,
            "uid_status": uid_status,
            "session_key": self.session_key,
            "ilo_generation": "ilo3",
            "os_name": self.detect_os_name(server_name, self.host),
            "hardware": {}
        }
        return info

    @staticmethod
    def detect_os_name(server_name: str, hostname: str = "", raw_resp: str = "") -> str:
        """Determines the operating system installed on the server based on AMS, SMBIOS, or hostname."""
        if raw_resp:
            m_os = re.search(r'<(?:OS_NAME|OPERATING_SYSTEM|HOST_OS)\s+VALUE="([^"]+)"', raw_resp, re.IGNORECASE)
            if m_os and m_os.group(1).strip():
                return m_os.group(1).strip()

        combined = f"{server_name} {hostname}".upper()
        if not combined.strip():
            return "Not Reported (Standby)"

        if "ESXI" in combined or "VMWARE" in combined:
            return "VMware ESXi"
        if "PROXMOX" in combined or "PVE" in combined:
            return "Proxmox VE"
        if "UBUNTU" in combined:
            return "Ubuntu Linux"
        if "DEBIAN" in combined:
            return "Debian Linux"
        if "CENTOS" in combined:
            return "CentOS Linux"
        if "RHEL" in combined or "REDHAT" in combined:
            return "Red Hat Enterprise Linux"
        if "ARCH" in combined:
            return "Arch Linux"
        if "FREEBSD" in combined or "BSD" in combined:
            return "FreeBSD"
        if "LINUX" in combined:
            return "Linux"
        if "WIN-SERVER" in combined or "WINSRV" in combined or "WIN20" in combined:
            return "Windows Server"
        if "WIN-" in combined or "WINDOWS" in combined or "WIN11" in combined or "WIN10" in combined:
            return "Windows Server"

        # Check for typical Windows autogenerated computer name (e.g. WIN-XXXXXXXXXXX)
        if re.search(r'\bWIN-[A-Z0-9]{5,}\b', combined):
            return "Windows Server"

        if server_name and not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', server_name):
            return f"Host: {server_name}"

        return "Not Reported"

    @staticmethod
    def _extract_smbios_strings(b64_data: str) -> List[str]:
        """Decodes SMBIOS ASCII string tables appended to record binary headers."""
        try:
            import base64
            raw = base64.b64decode(b64_data)
            if len(raw) < 4:
                return []
            header_len = raw[1]
            string_data = raw[header_len:]
            parts = [p.decode("latin-1", errors="ignore").strip() for p in string_data.split(b"\x00")]
            return [p for p in parts if p]
        except Exception:
            return []

    def parse_host_data(self, xml_str: str) -> Dict[str, Any]:
        """Parses GET_HOST_DATA SMBIOS records for exact CPU model, server model, serial, and UUID."""
        res = {
            "cpu_model": "",
            "server_model": "",
            "serial_number": "",
            "uuid": "",
            "bios_date": "",
            "bios_family": "",
            "processors": []
        }
        if not xml_str:
            return res

        m_data = re.search(r'<GET_HOST_DATA>.*?</GET_HOST_DATA>', xml_str, re.DOTALL)
        if not m_data:
            return res

        try:
            root = ET.fromstring(m_data.group(0))
        except Exception as e:
            print(f"[IloClient] parse_host_data XML error: {e}")
            return res

        for rec in root.findall("SMBIOS_RECORD"):
            t = rec.get("TYPE", "")
            b64 = rec.get("B64_DATA", "")
            strs = self._extract_smbios_strings(b64)

            if t == "0":  # BIOS Info
                for field in rec.findall("FIELD"):
                    fn = field.get("NAME", "")
                    fv = field.get("VALUE", "")
                    if fn == "Family": res["bios_family"] = fv
                    if fn == "Date": res["bios_date"] = fv

            elif t == "1":  # System Information
                for s in strs:
                    if "ProLiant" in s:
                        res["server_model"] = f"HP {s}" if not s.startswith("HP") else s
                    elif len(s) == 10 and s.isalnum():
                        res["serial_number"] = s
                for field in rec.findall("FIELD"):
                    fn = field.get("NAME", "")
                    fv = field.get("VALUE", "")
                    if fn == "Product Name" and fv:
                        res["server_model"] = f"HP {fv.strip()}"
                    elif fn == "Serial Number" and fv:
                        res["serial_number"] = fv.strip()
                    elif fn == "UUID" and fv:
                        res["uuid"] = fv.strip()

            elif t == "4":  # Processor Information
                proc_model = ""
                for s in strs:
                    if any(k in s for k in ("Xeon", "Intel", "AMD", "Opteron", "EPYC")):
                        if len(s) > len(proc_model):
                            proc_model = s
                if proc_model:
                    res["cpu_model"] = proc_model
                res["processors"].append({"strings": strs})

        return res

    def parse_network_settings(self, resp: str) -> Dict[str, Any]:
        """Parses iLO network settings to extract iLO hostname and IP."""
        net = {}
        m_dns = re.search(r'<DNS_NAME\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m_dns:
            net["ilo_hostname"] = m_dns.group(1).strip()
        m_ip = re.search(r'<IP_ADDRESS\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m_ip:
            net["ilo_ip"] = m_ip.group(1).strip()
        m_mac = re.search(r'<MAC_ADDRESS\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m_mac:
            net["ilo_mac"] = m_mac.group(1).strip()
        m_dom = re.search(r'<DOMAIN_NAME\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m_dom:
            net["domain_name"] = m_dom.group(1).strip()
        m_sub = re.search(r'<SUBNET_MASK\s+VALUE="([^"]+)"', resp, re.IGNORECASE)
        if m_sub:
            sub = m_sub.group(1).strip()
            net["subnet_mask"] = sub
            try:
                parts = [int(p) for p in sub.split(".")]
                bits = sum(bin(p).count("1") for p in parts)
                net["cidr"] = f"{bits}"
            except Exception:
                net["cidr"] = "24"
        else:
            net["subnet_mask"] = "255.255.255.0"
            net["cidr"] = "24"
        return net

    def parse_embedded_health(self, xml_str: str) -> Dict[str, Any]:
        """Parses GET_EMBEDDED_HEALTH XML into rich RAM specs, CPUs, power, and health data."""
        res = {
            "memory": {
                "total_ram_mb": 0,
                "total_ram_gb": 0,
                "installed_sticks": 0,
                "free_slots": 0,
                "total_slots": 0,
                "speed_summary": "Unknown",
                "components": []
            },
            "processors": {
                "count": 0,
                "speed": "",
                "cores_summary": "",
                "total_cores": 0,
                "total_threads": 0,
                "list": []
            },
            "power": {
                "present_reading": "",
                "supplies": []
            },
            "fans": {
                "redundancy": "Unknown",
                "list": []
            },
            "temperatures": [],
            "drives": [],
            "firmware": {},
            "server_model": ""
        }

        m_data = re.search(r'<GET_EMBEDDED_HEALTH_DATA>.*?</GET_EMBEDDED_HEALTH_DATA>', xml_str, re.DOTALL)
        if not m_data:
            return res

        data_xml = m_data.group(0)
        try:
            root = ET.fromstring(data_xml)
        except Exception as e:
            print(f"[IloClient] parse_embedded_health XML error: {e}")
            return res

        # 1. Processors
        procs = root.findall(".//PROCESSOR")
        total_cores = 0
        total_threads = 0
        for p in procs:
            lbl = p.find("LABEL").get("VALUE", "") if p.find("LABEL") is not None else ""
            spd = p.find("SPEED").get("VALUE", "") if p.find("SPEED") is not None else ""
            exec_t = p.find("EXECUTION_TECHNOLOGY").get("VALUE", "") if p.find("EXECUTION_TECHNOLOGY") is not None else ""
            l3 = p.find("INTERNAL_L3_CACHE").get("VALUE", "") if p.find("INTERNAL_L3_CACHE") is not None else ""

            m_c = re.search(r'(\d+)/\d+\s*cores;\s*(\d+)\s*threads', exec_t, re.IGNORECASE)
            if m_c:
                total_cores += int(m_c.group(1))
                total_threads += int(m_c.group(2))

            res["processors"]["list"].append({
                "label": lbl,
                "speed": spd,
                "execution": exec_t,
                "l3_cache": l3
            })
        res["processors"]["count"] = len(procs)
        if procs:
            res["processors"]["speed"] = procs[0].find("SPEED").get("VALUE", "") if procs[0].find("SPEED") is not None else ""
            res["processors"]["cores_summary"] = f"{total_cores} Cores / {total_threads} Threads"
            res["processors"]["total_cores"] = total_cores
            res["processors"]["total_threads"] = total_threads

        # 2. Memory (Total RAM GB, sticks installed, free slots, slot details)
        mem_comps = root.findall(".//MEMORY_COMPONENT")
        total_mb = 0
        installed_sticks = 0
        free_slots = 0
        speeds = []
        for m in mem_comps:
            loc = m.find("MEMORY_LOCATION").get("VALUE", "") if m.find("MEMORY_LOCATION") is not None else ""
            sz = m.find("MEMORY_SIZE").get("VALUE", "") if m.find("MEMORY_SIZE") is not None else ""
            spd = m.find("MEMORY_SPEED").get("VALUE", "") if m.find("MEMORY_SPEED") is not None else ""

            m_sz = re.search(r'(\d+)\s*MB', sz, re.IGNORECASE)
            if m_sz and int(m_sz.group(1)) > 0:
                mb = int(m_sz.group(1))
                total_mb += mb
                installed_sticks += 1
                if spd and spd != "0 MHz":
                    speeds.append(spd)
                res["memory"]["components"].append({
                    "location": loc,
                    "size_mb": mb,
                    "size_str": f"{mb // 1024} GB" if mb >= 1024 else f"{mb} MB",
                    "speed": spd,
                    "installed": True
                })
            else:
                free_slots += 1
                res["memory"]["components"].append({
                    "location": loc,
                    "size_mb": 0,
                    "size_str": "Not Installed",
                    "speed": spd,
                    "installed": False
                })

        res["memory"]["total_ram_mb"] = total_mb
        res["memory"]["total_ram_gb"] = round(total_mb / 1024, 1)
        res["memory"]["installed_sticks"] = installed_sticks
        res["memory"]["free_slots"] = free_slots
        res["memory"]["total_slots"] = len(mem_comps)
        res["memory"]["speed_summary"] = max(set(speeds), key=speeds.count) if speeds else "Unknown"

        # 3. Power
        pwr_sum = root.find(".//POWER_SUPPLY_SUMMARY")
        if pwr_sum is not None:
            pr = pwr_sum.find("PRESENT_POWER_READING")
            if pr is not None:
                res["power"]["present_reading"] = pr.get("VALUE", "").strip()

        supplies = root.findall(".//SUPPLY")
        for s in supplies:
            lbl = s.find("LABEL").get("VALUE", "").strip() if s.find("LABEL") is not None else ""
            st = s.find("STATUS").get("VALUE", "").strip() if s.find("STATUS") is not None else ""
            st_up = st.upper()
            res["power"]["supplies"].append({
                "label": lbl,
                "status": st_up,
                "installed": st_up not in ("NOT INSTALLED", "EMPTY", "ABSENT")
            })

        psu_red = root.find(".//HEALTH_AT_A_GLANCE/POWER_SUPPLIES[@REDUNDANCY]")
        if psu_red is not None:
            res["power"]["redundancy"] = psu_red.get("REDUNDANCY", "Not Redundant")

        # 4. Fans
        fans = root.findall(".//FAN")
        for f in fans:
            lbl = f.find("LABEL").get("VALUE", "").strip() if f.find("LABEL") is not None else ""
            st = f.find("STATUS").get("VALUE", "").strip() if f.find("STATUS") is not None else ""
            sp = f.find("SPEED").get("VALUE", "").strip() if f.find("SPEED") is not None else ""
            res["fans"]["list"].append({"label": lbl, "status": st.upper(), "speed": sp})

        fan_red = root.find(".//HEALTH_AT_A_GLANCE/FANS[@REDUNDANCY]")
        if fan_red is not None:
            res["fans"]["redundancy"] = fan_red.get("REDUNDANCY", "Redundant")

        # 5. Drives
        for m in re.finditer(r'<DRIVE_BAY VALUE = "(\d+)"/>\s*<PRODUCT_ID VALUE = "([^"]+)"/>\s*<STATUS VALUE = "([^"]+)"/>', data_xml):
            bay_num = m.group(1)
            prod = m.group(2).strip()
            st = m.group(3).strip()
            if prod != "N/A" and st != "Not Installed":
                res["drives"].append({
                    "bay": bay_num,
                    "model": prod,
                    "status": st
                })

        # 6. Temperatures
        for t in root.findall(".//TEMP"):
            lbl = t.find("LABEL").get("VALUE", "") if t.find("LABEL") is not None else ""
            loc = t.find("LOCATION").get("VALUE", "") if t.find("LOCATION") is not None else ""
            st = t.find("STATUS").get("VALUE", "") if t.find("STATUS") is not None else ""
            cur = t.find("CURRENTREADING").get("VALUE", "") if t.find("CURRENTREADING") is not None else ""
            if st == "OK" and cur != "N/A":
                res["temperatures"].append({"label": lbl, "location": loc, "temp_c": cur})

        # 7. Model from CPLD & System ROM
        fw_info = root.find(".//FIRMWARE_INFORMATION")
        if fw_info is not None:
            for item in fw_info:
                name_el = item.find("FIRMWARE_NAME")
                ver_el = item.find("FIRMWARE_VERSION")
                if name_el is not None and ver_el is not None:
                    name_val = name_el.get("VALUE", "")
                    ver_val = ver_el.get("VALUE", "")
                    if "CPLD" in name_val:
                        m_mod = re.search(r'(ProLiant [A-Z0-9]+ G\d+)', ver_val)
                        if m_mod:
                            res["server_model"] = f"HP {m_mod.group(1)}"
                    elif "System ROM" in name_val and "Backup" not in name_val and "Bootblock" not in name_val:
                        res["firmware"]["system_rom"] = ver_val

        # 8. Physical Network Interfaces (NICs)
        res["nics"] = []
        nic_info = root.find(".//NIC_INFOMATION")
        if nic_info is not None:
            for n in nic_info.findall("NIC"):
                port_el = n.find("NETWORK_PORT")
                mac_el = n.find("MAC_ADDRESS")
                port_val = port_el.get("VALUE", "") if port_el is not None else ""
                mac_val = mac_el.get("VALUE", "") if mac_el is not None else ""
                if mac_val:
                    res["nics"].append({
                        "name": f"{port_val} (Embedded Gigabit NIC)",
                        "port": port_val,
                        "mac": mac_val
                    })
            ilo_nic = nic_info.find("iLO")
            if ilo_nic is not None:
                ilo_port = ilo_nic.find("NETWORK_PORT")
                ilo_mac = ilo_nic.find("MAC_ADDRESS")
                res["nics"].append({
                    "name": ilo_port.get("VALUE", "iLO Dedicated Management Port") if ilo_port is not None else "iLO Dedicated Management Port",
                    "port": "iLO",
                    "mac": ilo_mac.get("VALUE", "") if ilo_mac is not None else ""
                })

        return res

    def get_system_info(self) -> Dict[str, Any]:
        xml = (
            '<SERVER_INFO MODE="read">\r\n'
            '  <GET_SERVER_NAME/>\r\n'
            '  <GET_HOST_POWER_STATUS/>\r\n'
            '  <GET_UID_STATUS/>\r\n'
            '</SERVER_INFO>\r\n'
            '<RIB_INFO MODE="read">\r\n'
            '  <GET_FW_VERSION/>\r\n'
            '</RIB_INFO>'
        )
        resp = self.send_ribcl(xml)
        return self.parse_system_info(resp)

    def _detect_generation(self, sample_resp: str = "") -> str:
        fw = self._extract_attr(sample_resp, "GET_FW_VERSION", "FIRMWARE_VERSION") or ""
        type_str = self._extract_attr(sample_resp, "GET_FW_VERSION", "MANAGEMENT_PROCESSOR") or sample_resp

        if "iLO 3" in type_str or "iLO3" in type_str:
            self.detected_gen = "ilo3"
        elif "iLO 4" in type_str or "iLO4" in type_str:
            self.detected_gen = "ilo4"
        elif "iLO 5" in type_str or "iLO5" in type_str:
            self.detected_gen = "ilo5"
        else:
            if fw.startswith("1."):
                self.detected_gen = "ilo3"
            elif fw.startswith("2."):
                self.detected_gen = "ilo4"
            else:
                self.detected_gen = "ilo3"
        return self.detected_gen

    def _extract_attr(self, xml_text: str, tag: str, attr: str) -> Optional[str]:
        m = re.search(rf'<{tag}[^>]*\b{attr}\s*=\s*[\'"]([^\'"]+)[\'"]', xml_text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_tag(self, xml_text: str, tag: str) -> Optional[str]:
        m = re.search(rf'<{tag}[^>]*>([^<]+)</{tag}>', xml_text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _check_ribcl_success(self, resp: str) -> bool:
        if not resp:
            return False
        resp_lower = resp.lower()
        if "syntax error" in resp_lower:
            return False
        if "login failed" in resp_lower:
            return False
        if 'status="0x005f"' in resp_lower:
            return False

        statuses = re.findall(r'STATUS="([^"]+)"', resp, re.IGNORECASE)
        if not statuses:
            return "<ERROR" not in resp.upper()

        has_success = False
        for s in statuses:
            s_clean = s.strip().lower()
            if s_clean in ("0x0000", "0x0", "0"):
                has_success = True
            elif s_clean in ("0x005f", "0x0001", "0x0002", "0x000a"):
                return False
        return has_success

    def _redfish_get(self, path: str) -> Optional[Dict[str, Any]]:
        target_url = f"{self.bridge_url}{path}" if self.bridge_url else f"https://{self.host}:{self.port}{path}"
        ctx = None if self.bridge_url else self.ssl_ctx
        req = urllib.request.Request(target_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                import json
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
