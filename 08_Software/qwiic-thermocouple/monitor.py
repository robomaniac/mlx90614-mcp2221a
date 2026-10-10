"""Loopback dashboard server. One worker owns HID; HTTP never reads USB directly."""
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import csv
import json
import secrets
import threading
import time
import webbrowser

from sensor import ReadError, open_sensor

ROOT = Path(__file__).resolve().parent
FIELDS = ("sequence", "timestamp_ms", "status", "hot_c", "cold_c", "hot_raw", "cold_raw",
          "sensor_status", "acquisition_ms", "error_code", "error")
RATES = (1, 2, 4)


class Monitor:
    def __init__(self, address=0x60, device_index=None, factory=None):
        self.address, self.device_index = address, device_index
        self.factory = factory or (lambda: open_sensor(self.address, self.device_index))
        self.lock = threading.Lock()
        self.lifecycle = threading.Lock()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.path = None
        self.reset()

    def reset(self):
        self.phase, self.message, self.rate, self.info = "disconnected", "Ready to connect", 2, None
        self.attempts = self.valid = self.failed = 0
        self.started_ms = self.ended_ms = self.last_sample_ms = None
        self.history, self.logs = deque(maxlen=1200), deque(maxlen=100)

    def log(self, message):
        self.logs.append({"timestamp_ms": round(time.time() * 1000), "message": message})

    def connect(self, rate=2):
        if rate not in RATES:
            raise ValueError("Poll rate must be 1, 2 or 4 Hz.")
        with self.lifecycle:
            if self.thread and self.thread.is_alive():
                return
            self.stop.clear()
            self.ready.clear()
            with self.lock:
                self.reset()
                self.path = None
                self.rate, self.phase, self.message = rate, "connecting", "Checking the bridge and sensor"
            self.thread = threading.Thread(target=self.run, name="thermocouple-reader", daemon=True)
            self.thread.start()
            self.ready.wait(2)

    def disconnect(self):
        with self.lifecycle:
            self.stop.set()
            if self.thread:
                self.thread.join(3)
                if self.thread.is_alive():
                    raise RuntimeError("Reader is still stopping; wait before reconnecting.")

    def set_rate(self, rate):
        if rate not in RATES:
            raise ValueError("Poll rate must be 1, 2 or 4 Hz.")
        with self.lock:
            self.rate = rate
            self.log(f"Polling changed to {rate} Hz; sensor configuration preserved.")

    def snapshot(self):
        with self.lock:
            end = self.ended_ms or round(time.time() * 1000)
            elapsed = (end - self.started_ms) / 1000 if self.started_ms else 0
            return {"transport": "native", "phase": self.phase, "message": self.message,
                    "rate": self.rate, "info": self.info, "attempts": self.attempts,
                    "valid": self.valid, "failed": self.failed, "last_sample_ms": self.last_sample_ms,
                    "elapsed_s": elapsed, "actual_hz": self.valid / elapsed if elapsed else 0,
                    "history": list(self.history), "logs": list(self.logs),
                    "csv_available": self.path is not None and self.path.is_file()}

    def run(self):
        sensor = None
        try:
            sensor = self.factory()
            info = sensor.identify()
            output = ROOT / "output"
            output.mkdir(exist_ok=True)
            name = "thermocouple_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + ".csv"
            path = output / name
            with path.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                stream.flush()
                with self.lock:
                    self.path, self.info = path, info
                    self.started_ms = round(time.time() * 1000)
                    self.phase, self.message = "live", "Reading thermocouple and board temperatures"
                    self.log(f"MCP9600 ID {info['device_id']} at 0x{info['address']:02X}; Type {info['thermocouple_type']}, {info['adc_bits']}-bit, 100 kHz. No USB reset.")
                self.ready.set()
                deadline = time.perf_counter()
                while not self.stop.is_set():
                    if self.stop.wait(max(0, deadline - time.perf_counter())):
                        break
                    start = time.perf_counter()
                    with self.lock:
                        self.attempts += 1
                        sequence = self.attempts
                    row = dict.fromkeys(FIELDS, "")
                    row.update(sequence=sequence, status="ok")
                    try:
                        row.update(sensor.sample())
                    except ReadError as error:
                        row.update(status="error", error_code=error.code, error=str(error))
                    row.update(timestamp_ms=round(time.time() * 1000),
                               acquisition_ms=round((time.perf_counter() - start) * 1000, 4))
                    writer.writerow(row)
                    stream.flush()
                    with self.lock:
                        self.history.append(row)
                        if row["status"] == "ok":
                            self.valid += 1
                            self.last_sample_ms = row["timestamp_ms"]
                        else:
                            self.failed += 1
                            self.phase, self.message = "error", row["error"]
                            self.log(f"Stopped: {row['error_code']}: {row['error']}")
                        period = 1 / self.rate
                    if row["status"] != "ok":
                        break  # Retain errors; no hidden retries, cancellation or USB reset.
                    deadline += period
                    now = time.perf_counter()
                    if deadline < now:
                        deadline += ((now - deadline) // period + 1) * period
        except Exception as error:
            with self.lock:
                self.phase, self.message = "error", str(error)
                self.log(f"Connection stopped: {getattr(error, 'code', type(error).__name__)}: {error}")
        finally:
            if sensor:
                try:
                    sensor.close()
                except Exception as error:
                    with self.lock:
                        self.phase, self.message = "error", f"Could not close the bridge: {error}"
                        self.log(self.message)
            with self.lock:
                self.ended_ms = round(time.time() * 1000)
                if self.phase != "error":
                    self.phase, self.message = "disconnected", "Disconnected; readings and CSV retained"
                    self.log("HID handle closed. Another sensor reader can connect.")
            self.ready.set()


def make_handler(monitor, origin, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data, content_type="application/json"):
            body = json.dumps(data, allow_nan=False).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            if self.headers.get("Host") != origin.removeprefix("http://"):
                self.send(403, {"error": "Use the loopback dashboard URL."})
                return False
            return True

        def do_GET(self):
            if not self.valid_host():
                return
            if self.path in ("/", "/thermocouple.html"):
                self.send(200, (ROOT / "thermocouple.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/session":
                self.send(200, {"kind": "qwiic-native-monitor", "token": token})
            elif self.path == "/api/state":
                self.send(200, monitor.snapshot())
            elif self.path == "/api/csv":
                with monitor.lock:
                    path = monitor.path
                if path and path.is_file():
                    self.send(200, path.read_bytes(), "text/csv; charset=utf-8")
                else:
                    self.send(404, {"error": "No measurements recorded yet."})
            elif self.path == "/favicon.ico":
                self.send(204, b"", "image/x-icon")
            else:
                self.send(404, {"error": "Not found."})

        def do_POST(self):
            if not self.valid_host():
                return
            if (self.headers.get("Origin") != origin or self.headers.get("X-Monitor-Token") != token
                    or self.headers.get("Content-Type") != "application/json"):
                self.send(403, {"error": "Use the controls in this dashboard."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 1024:
                    raise ValueError("Request is too large.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object.")
                if self.path == "/api/connect":
                    monitor.connect(data.get("rate", 2))
                elif self.path == "/api/disconnect":
                    monitor.disconnect()
                elif self.path == "/api/rate":
                    monitor.set_rate(data.get("rate"))
                elif self.path == "/api/shutdown":
                    monitor.disconnect()
                    self.send(200, monitor.snapshot())
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                else:
                    self.send(404, {"error": "Not found."})
                    return
                self.send(200, monitor.snapshot())
            except (ValueError, TypeError, RuntimeError) as error:
                self.send(400, {"error": str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--address", type=lambda text: int(text, 0), default=0x60)
    parser.add_argument("--device-index", type=int)
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not 0x60 <= args.address <= 0x67:
        parser.error("Use port 1024..65535 and address 0x60..0x67.")
    origin = f"http://127.0.0.1:{args.port}"
    monitor = Monitor(args.address, args.device_index)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(monitor, origin, secrets.token_urlsafe(24)))
    print(f"Thermocouple dashboard: {origin}", flush=True)
    print("Native Cython/HIDAPI reused. Ctrl+C stops the server and closes the bridge.", flush=True)
    try:
        if args.connect:
            monitor.connect()
            print(f"Sensor: {monitor.snapshot()['phase']}", flush=True)
        if not args.no_browser:
            webbrowser.open(origin)
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        print("Stopping.", flush=True)
    finally:
        monitor.disconnect()
        server.server_close()


if __name__ == "__main__":
    main()
