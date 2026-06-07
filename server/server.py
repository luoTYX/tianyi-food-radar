"""
天依的美食雷达 - 位置接收服务 (零依赖版)
手机Tasker定时POST位置过来，AstrBot插件按需拉取
纯标准库，不依赖任何第三方包
"""
import json
import time
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "location_data.json")
SECRET = "tianyi_food_radar_2024"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode())

    def _check_secret(self):
        """检查密钥，返回True=通过"""
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if self.command == "POST":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode()
            try:
                body = json.loads(raw)
            except Exception:
                body = {}
            return body.get("secret") == SECRET
        else:
            return qs.get("secret", [""])[0] == SECRET

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/location":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode()
            try:
                body = json.loads(raw)
            except Exception:
                self._send_json(403, {"ok": False, "msg": "数据格式不对"})
                return

            if body.get("secret") != SECRET:
                self._send_json(403, {"ok": False, "msg": "密钥不对哦"})
                return

            lat = body.get("lat")
            lng = body.get("lng")
            if lat is None or lng is None:
                self._send_json(400, {"ok": False, "msg": "经纬度呢"})
                return

            data = {
                "lat": float(lat),
                "lng": float(lng),
                "accuracy": float(body.get("accuracy", 0)),
                "updated_at": datetime.now().isoformat(),
                "timestamp": time.time(),
            }
            save_data(data)
            self._send_json(200, {"ok": True, "msg": "好嘞 位置收到啦~"})
        else:
            self._send_json(404, {"ok": False, "msg": "不知道这接口"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/location/latest":
            if qs.get("secret", [""])[0] != SECRET:
                self._send_json(403, {"ok": False, "msg": "密钥不对哦"})
                return
            data = load_data()
            if not data:
                self._send_json(200, {"ok": False, "msg": "还没收到过位置呢"})
                return
            self._send_json(200, {"ok": True, "data": data})

        elif path == "/api/health":
            self._send_json(200, {"ok": True, "msg": "天依的美食雷达运行中~"})

        else:
            self._send_json(404, {"ok": False, "msg": "不知道这接口"})


if __name__ == "__main__":
    port = 8899
    print(f"天依的美食雷达启动... 端口{port}")
    server = HTTPServer(("0.0.0.0", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
