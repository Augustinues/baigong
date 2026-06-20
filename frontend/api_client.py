"""百工 API 客户端 — HTTP 请求 + SSE 订阅"""

import json
import logging
import queue
import threading
import time
import urllib.request
import urllib.error

logger = logging.getLogger("baigong.api")

SERVER_URL = "http://127.0.0.1:8000"


def api_get(path: str) -> dict:
    """GET 请求"""
    try:
        r = urllib.request.urlopen(f"{SERVER_URL}{path}", timeout=10)
        return json.loads(r.read().decode())
    except Exception as e:
        logger.debug(f"GET {path} failed: {e}")
        return {"error": str(e)}


def api_post(path: str, body: dict = None) -> dict:
    """POST 请求"""
    try:
        data = json.dumps(body or {}).encode()
        r = urllib.request.urlopen(
            f"{SERVER_URL}{path}",
            data=data,
            timeout=10,
        )
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_patch(path: str, body: dict) -> dict:
    """PATCH 请求"""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{SERVER_URL}{path}",
            data=data,
            method="PATCH",
            headers={"Content-Type": "application/json"},
        )
        r = urllib.request.urlopen(req, timeout=10)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_delete(path: str) -> dict:
    """DELETE 请求"""
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}{path}",
            method="DELETE",
        )
        r = urllib.request.urlopen(req, timeout=10)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class SSEThread(threading.Thread):
    """SSE 事件流订阅线程"""

    def __init__(self, url: str, callback, interval: float = 2.0):
        super().__init__(daemon=True)
        self._url = f"{SERVER_URL}{url}"
        self._callback = callback
        self._interval = interval
        self._running = True

    def run(self):
        while self._running:
            try:
                r = urllib.request.urlopen(self._url, timeout=self._interval + 1)
                for line in r:
                    if not self._running:
                        return
                    if line.startswith(b"data: "):
                        data = json.loads(line[6:].decode())
                        self._callback(data)
            except Exception:
                pass
            time.sleep(self._interval)

    def stop(self):
        self._running = False
