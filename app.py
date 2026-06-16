import json
import os
import time
from datetime import datetime
from collections import defaultdict

from flask import Flask, render_template
from flask_socketio import SocketIO
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

LOG_FILE = os.path.expanduser("~cowrie/cowrie/var/log/cowrie/cowrie.json")

stats = {
    "total_events": 0,
    "unique_ips": set(),
    "login_attempts": 0,
    "login_success": 0,
    "commands_run": [],
    "events": [],
    "ips": defaultdict(int),
    "usernames": defaultdict(int),
    "passwords": defaultdict(int),
    "event_types": defaultdict(int),
}

def parse_log_line(line):
    line = line.strip()
    if not line:
        return
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return

    ev = entry.get("eventid", "")
    src_ip = entry.get("src_ip", "unknown")
    timestamp = entry.get("timestamp", "")

    stats["total_events"] += 1
    stats["unique_ips"].add(src_ip)
    stats["ips"][src_ip] += 1
    stats["event_types"][ev] += 1

    event_data = {
        "time": timestamp,
        "ip": src_ip,
        "event": ev,
        "detail": ""
    }

    if ev == "cowrie.login.failed":
        stats["login_attempts"] += 1
        user = entry.get("username", "")
        pwd  = entry.get("password", "")
        stats["usernames"][user] += 1
        stats["passwords"][pwd]  += 1
        event_data["detail"] = f"{user}:{pwd}"

    elif ev == "cowrie.login.success":
        stats["login_success"] += 1
        event_data["detail"] = f"{entry.get('username','')}:{entry.get('password','')}"

    elif ev == "cowrie.command.input":
        cmd = entry.get("input", "")
        stats["commands_run"].append({"ip": src_ip, "cmd": cmd, "time": timestamp})
        event_data["detail"] = cmd

    elif ev == "cowrie.session.connect":
        event_data["detail"] = f"port {entry.get('dst_port','')}"

    stats["events"].insert(0, event_data)
    stats["events"] = stats["events"][:200]  # keep last 200

    socketio.emit("update", build_payload())

def build_payload():
    return {
        "total_events":    stats["total_events"],
        "unique_ips":      len(stats["unique_ips"]),
        "login_attempts":  stats["login_attempts"],
        "login_success":   stats["login_success"],
        "events":          stats["events"][:50],
        "top_ips":         sorted(stats["ips"].items(), key=lambda x: x[1], reverse=True)[:8],
        "top_usernames":   sorted(stats["usernames"].items(), key=lambda x: x[1], reverse=True)[:8],
        "top_passwords":   sorted(stats["passwords"].items(), key=lambda x: x[1], reverse=True)[:8],
        "event_types":     dict(stats["event_types"]),
        "commands":        stats["commands_run"][-20:],
    }

class LogHandler(FileSystemEventHandler):
    def __init__(self):
        self._pos = 0
        # Read existing log content on startup
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                for line in f:
                    parse_log_line(line)
            self._pos = os.path.getsize(LOG_FILE)

    def on_modified(self, event):
        if event.src_path != LOG_FILE:
            return
        with open(LOG_FILE, "r") as f:
            f.seek(self._pos)
            for line in f:
                parse_log_line(line)
            self._pos = f.tell()

def start_watcher():
    handler = LogHandler()
    observer = Observer()
    observer.schedule(handler, path=os.path.dirname(LOG_FILE), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("connect")
def on_connect():
    socketio.emit("update", build_payload())

if __name__ == "__main__":
    t = threading.Thread(target=start_watcher, daemon=True)
    t.start()
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
