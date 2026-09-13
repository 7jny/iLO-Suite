import os
import json
import uuid

STORE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servers.json")

class ServerStore:
    def __init__(self, file_path=STORE_FILE):
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            initial_data = [
                {
                    "id": "sample-ilo3",
                    "name": "HP ProLiant DL380 G7 (Beispiel)",
                    "host": "192.168.1.150",
                    "port": 443,
                    "ilo_version": "ilo3",
                    "user": "Administrator",
                    "password": "",
                    "notes": "Beispielkonfiguration f\u00fcr einen ProLiant G7 Server mit iLO 3"
                }
            ]
            self.save_all(initial_data)

    def get_all(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[ServerStore] Error loading servers: {e}")
        return []

    def save_all(self, servers):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ServerStore] Error saving servers: {e}")
            return False

    def add_or_update(self, server_data):
        servers = self.get_all()
        s_id = server_data.get("id")

        matched_idx = -1
        if s_id:
            for idx, s in enumerate(servers):
                if s.get("id") == s_id:
                    matched_idx = idx
                    break
        else:
            host = server_data.get("host")
            port = server_data.get("port", 443)
            for idx, s in enumerate(servers):
                if s.get("host") == host and s.get("port", 443) == port:
                    matched_idx = idx
                    s_id = s.get("id")
                    break

        if matched_idx != -1:
            existing = servers.pop(matched_idx)
            if not server_data.get("password") and existing.get("password"):
                server_data["password"] = existing["password"]
            server_data["id"] = s_id
            servers.insert(0, server_data)
        else:
            if not s_id:
                s_id = str(uuid.uuid4())[:8]
            server_data["id"] = s_id
            servers.insert(0, server_data)

        self.save_all(servers)
        return server_data

    def delete(self, server_id):
        servers = self.get_all()
        filtered = [s for s in servers if s.get("id") != server_id]
        if len(filtered) != len(servers):
            self.save_all(filtered)
            return True
        return False

    def get_by_id(self, server_id):
        for s in self.get_all():
            if s.get("id") == server_id:
                return s
        return None
