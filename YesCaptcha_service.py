import os
import time
import json
from dotenv import load_dotenv
from curl_cffi import requests

load_dotenv()

# Boterdrop-Solver (Camoufox — works from VPS without residential proxy)
SOLVER_URL = os.getenv('SOLVER_URL', 'http://localhost:8123')


class TurnstileService:
    def __init__(self):
        self.base_url = SOLVER_URL
        self.session = requests.Session(impersonate="chrome")

    def create_task(self, siteurl, sitekey):
        """Create turnstile solve task via Boterdrop-Solver"""
        self._siteurl = siteurl
        self._sitekey = sitekey
        req_url = f"{self.base_url}/turnstile?url={siteurl}&sitekey={sitekey}"
        try:
            r = self.session.get(req_url, timeout=30)
            data = r.json()
            self._task_id = data.get("task_id", "")
            return self._task_id
        except Exception as e:
            print(f"[-] Boterdrop-Solver create task failed: {e}")
            return None

    def get_response(self, task_id, max_retries=3, initial_delay=2, retry_delay=3):
        """Poll Boterdrop-Solver for result"""
        time.sleep(initial_delay)
        tid = task_id or getattr(self, '_task_id', None)
        if not tid:
            print("[-] No task_id to poll")
            return None

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            time.sleep(2)
            try:
                r = self.session.get(f"{self.base_url}/result?id={tid}", timeout=30)
                result = r.json()
                status = result.get("status", "")
                if status == "success":
                    token = result.get("value", "")
                    elapsed = result.get("elapsed_time", 0)
                    print(f"[+] Turnstile solved ({elapsed}s), len={len(token)}")
                    return token
                elif status == "error":
                    print(f"[-] Boterdrop-Solver error: {result}")
                    return None
            except Exception as e:
                print(f"[-] Boterdrop-Solver poll error: {e}")
                return None

        print("[-] Boterdrop-Solver timed out")
        return None
