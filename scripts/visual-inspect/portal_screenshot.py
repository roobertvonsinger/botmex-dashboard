"""Visual inspector for /portal — launches a mock server and takes screenshots.

Usage: python scripts/visual-inspect/portal_screenshot.py
Requires: playwright installed (playwright install chromium)

Originally built during the 2026-08-03 rebrand session. Anonymized for repo.
"""
import http.server
import json
import os
import socketserver
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 5099
ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)
SCREENSHOT_DIR = os.path.join(ROOT_DIR, "_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

MOCK_ACCOUNTS = [
    {"id": 1, "email": "user1@example.com", "balance_real": 1450.00, "balance_bonos": 320.50,
     "last_deposit_amount": 150.00, "last_deposit_date": "2026-08-02T14:30:00Z", "grade": "A+",
     "is_locked": True, "status": "LIVE", "clabe_stp": "646180157000000001"},
    {"id": 2, "email": "user2@example.com", "balance_real": 890.00, "balance_bonos": 150.00,
     "last_deposit_amount": 150.00, "last_deposit_date": "2026-08-02T10:15:00Z", "grade": "A",
     "is_locked": False, "status": "LIVE", "clabe_stp": "646180157000000002"},
    {"id": 3, "email": "user3@example.com", "balance_real": 270.00, "balance_bonos": 50.00,
     "last_deposit_amount": 150.00, "last_deposit_date": "2026-08-01T18:45:00Z", "grade": "B",
     "is_locked": False, "status": "LIVE", "clabe_stp": ""},
    {"id": 4, "email": "user4@example.com", "balance_real": 60.00, "balance_bonos": 0,
     "last_deposit_amount": 150.00, "last_deposit_date": "2026-08-01T09:20:00Z", "grade": "C",
     "is_locked": True, "status": "LIVE", "clabe_stp": "646180157000000004"},
]

MOCK_MISSION_SCHED = {
    "mission_id": "a3f8b2c1",
    "status": "scheduling",
    "phase_detail": "2 matches — 9x$150/60s",
    "total_deposited": 300.0,
    "total_approved": 2,
    "total_failed": 0,
    "matches": json.dumps([
        {"email": "user1@example.com", "card_pipe": "4111...1234", "clabe_stp": "646180157000000001"},
        {"email": "user2@example.com", "card_pipe": "5579...5678", "clabe_stp": "646180157000000002"}
    ]),
}

MOCK_MISSION_DONE = {
    "mission_id": "a3f8b2c1",
    "status": "completed",
    "phase_detail": "$1350 en 2 cuentas",
    "total_deposited": 1350.0,
    "total_approved": 9,
    "total_failed": 0,
    "matches": json.dumps([
        {"email": "user1@example.com", "card_pipe": "4111...1234", "clabe_stp": "646180157000000001"},
        {"email": "user2@example.com", "card_pipe": "5579...5678", "clabe_stp": "646180157000000002"}
    ]),
}

class MockHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/portal.html"):
            self.path = "/static/portal.html" + self.path[12:]
            return super().do_GET()
        if self.path.startswith("/api/operator/my-accounts"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "accounts": MOCK_ACCOUNTS}).encode())
            return
        if self.path.startswith("/api/deposits/auto/") and self.path.endswith("/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = MOCK_MISSION_DONE if "done" in self.path else MOCK_MISSION_SCHED
            self.wfile.write(json.dumps(data).encode())
            return
        if self.path.startswith("/api/events"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass

def main():
    server = socketserver.TCPServer(("127.0.0.1", PORT), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Accounts Desktop (1280x800)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/portal.html", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "portal-accounts-desktop.png"), full_page=True)
        ctx.close()

        # 2. Accounts Mobile (375x812 iPhone X)
        ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/portal.html", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "portal-accounts-mobile.png"), full_page=True)
        ctx.close()

        # 3. Mission View Desktop (?match=a3f8b2c1)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/portal.html?match=a3f8b2c1", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "portal-mission-desktop.png"), full_page=True)
        ctx.close()

        # 4. Mission Completed Desktop (?match=a3f8b2c1_done)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/portal.html?match=a3f8b2c1_done", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "portal-mission-done-desktop.png"), full_page=True)
        ctx.close()

        browser.close()

    print("[inspector] Screenshots renderizados OK.")

if __name__ == "__main__":
    main()
