"""Separate temperature-logger service. One worker serializes sensor and SD traffic."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import io
import json
import math
import queue
import secrets
import sys
import threading
import time
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'qwiic-thermocouple'))
from monitor import Monitor, make_handler, ThreadingHTTPServer
from sensor import ReadError
from sdcard import CardBus, OpenLog
from recovery import open_bridge, open_sensor_checked, clear_i2c_error

ROOT = Path(__file__).resolve().parent
FIELDS = ('sequence', 'timestamp_ms', 'timestamp_utc', 'status', 'probe_name', 'board_name',
          'hot_c', 'cold_c', 'hot_f', 'cold_f', 'hot_raw', 'cold_raw', 'sensor_status',
          'acquisition_ms', 'error_code', 'error')
DEFAULTS = dict(interval_s=.5, probe_name='Thermocouple', board_name='Board', sd=False, sd_address=42)


def settings(data, rate=None):
    if not isinstance(data, dict) or set(data) - set(DEFAULTS):
        raise ValueError('Unknown recording settings.')
    result = {**DEFAULTS, **data}
    interval = result['interval_s']
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not math.isfinite(interval):
        raise ValueError('Recording interval must be a finite number.')
    if not .25 <= interval <= 86400:
        raise ValueError('Use 0.25 seconds through 24 hours for sampling and recording.')
    for key in ('probe_name', 'board_name'):
        name = result[key]
        if not isinstance(name, str) or not name.strip() or len(name) > 40 or any(ord(c) < 32 for c in name):
            raise ValueError('Sensor names need 1..40 printable characters.')
        result[key] = name.strip()
    if not isinstance(result['sd'], bool) or result['sd_address'] not in (41, 42):
        raise ValueError('Use an SD checkbox and OpenLog address 0x29 or 0x2A.')
    return result


def decorate(row, cfg):
    row = {**row, 'timestamp_utc': datetime.fromtimestamp(row['timestamp_ms'] / 1000, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')}
    for key in ('probe_name', 'board_name'):
        name = cfg[key]
        row[key] = "'" + name if name.startswith(('=', '+', '-', '@')) else name
    if row['status'] == 'ok':
        row.update(hot_f=round(row['hot_c'] * 1.8 + 32, 4), cold_f=round(row['cold_c'] * 1.8 + 32, 4))
    return row


def csv_line(row=None):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, FIELDS, extrasaction='ignore')
    writer.writerow(row) if row is not None else writer.writeheader()
    return stream.getvalue()


class Logger(Monitor):
    def __init__(self, *args, card_factory=None, bridge_factory=None, **kwargs):
        self.cfg = DEFAULTS.copy()
        self.commands = queue.Queue(maxsize=4)
        self.card_factory = card_factory or (lambda sensor, address: OpenLog(CardBus(sensor.bridge), address))
        self.record_stream = None
        self.card = None
        self.wake = threading.Event()
        self.schedule_revision = 0
        super().__init__(*args, **kwargs)
        if kwargs.get('factory') is None:
            self.factory = lambda: open_sensor_checked(self.address, self.device_index)
        self.bridge_factory = bridge_factory or (lambda: open_bridge(self.address, self.device_index))

    def reset(self):
        super().reset()
        self.record_phase, self.record_message = 'idle', 'Choose an interval, then start recording.'
        self.record_path, self.record_count = None, 0
        self.sd_filename, self.sd_bytes = '', 0
        self.sd_phase, self.sd_error, self.sd_error_code = 'off', '', ''
        self.record_events = []

    def snapshot(self):
        result = super().snapshot()
        with self.lock:
            result['recording'] = dict(phase=self.record_phase, message=self.record_message,
                count=self.record_count, available=self.record_path is not None,
                sd_filename=self.sd_filename, sd_bytes=self.sd_bytes, settings=dict(self.cfg),
                sd_phase=self.sd_phase, sd_error=self.sd_error, sd_error_code=self.sd_error_code)
        return result

    def recover_bridge(self):
        with self.lifecycle:
            if self.thread and self.thread.is_alive():
                raise ValueError('Disconnect the reader before clearing the bridge error.' if self.phase == 'live' else 'Reader is still stopping. Wait a moment, then try Clear bridge error again.')
            bridge = None
            with self.lock:
                self.phase, self.message = 'recovering', 'Clearing the failed I2C transaction; USB stays connected.'
            try:
                bridge = self.bridge_factory()
                clear_i2c_error(bridge, self.log)
                bridge.close()
                bridge = None
                with self.lock:
                    self.phase, self.message = 'disconnected', 'Bridge ready. Click Connect. USB was not reset.'
            except Exception as error:
                with self.lock:
                    self.phase, self.message = 'error', str(error)
                    self.log('Bridge recovery failed: ' + str(error))
                raise ValueError(str(error)) from error
            finally:
                if bridge:
                    bridge.close()

    def sd_start_failed(self, sensor, error):
        self.sd_filename = self.card.filename or ''
        self.sd_error, self.sd_error_code = str(error), error.code
        self.sd_phase = 'unconfirmed' if self.sd_filename else 'unavailable'
        self.log(f'SD start failed: {error.code}: {error}')
        fault = decorate(dict(sequence=self.attempts, timestamp_ms=round(time.time() * 1000),
            status='logger_error', error_code=error.code, error=str(error)), self.cfg)
        self.record_stream.write(csv_line(fault)); self.record_stream.flush()
        self.record_count += 1
        self.record_events.append(fault)
        # Missing/malformed HID replies cannot be followed by another command.
        if error.code.startswith('HID_'):
            raise error
        clear_i2c_error(sensor.bridge, self.log)
        self.card = None
        self.log('SD disabled for this session; PC recording continues. No sensor sample was retried.')

    @staticmethod
    def validate_rate(rate):
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 1 / 86400 <= rate <= 4:
            raise ValueError('Sample interval must be 250 ms through 24 hours.')

    def connect(self, rate=2):
        self.validate_rate(rate)
        with self.lifecycle:
            if self.thread and self.thread.is_alive():
                return
            self.stop.clear()
            self.ready.clear()
            with self.lock:
                self.reset()
                self.path = None
                self.rate, self.phase, self.message = rate, 'connecting', 'Checking the bridge and sensor'
            self.thread = threading.Thread(target=self.run, name='temperature-logger-reader', daemon=True)
            self.thread.start()
            self.ready.wait(2)

    def set_rate(self, rate):
        self.validate_rate(rate)
        with self.lock:
            if self.record_phase == 'recording':
                raise ValueError('Stop recording before changing the sample interval.')
            self.rate = rate
            self.schedule_revision += 1
            self.log(f'Sample interval changed to {1 / rate:g} seconds; every recording poll is saved.')
        self.wake.set()

    def recording_action(self, action, config=None):
        if action not in ('start', 'stop'):
            raise ValueError('Unknown recording action.')
        with self.lock:
            if self.phase != 'live' or not self.thread or not self.thread.is_alive():
                raise ValueError('Connect the sensor before recording.')
            cfg = settings({} if config is None else config, self.rate) if action == 'start' else None
        event, result = threading.Event(), {}
        try:
            self.commands.put_nowait((action, cfg, event, result))
            self.wake.set()
        except queue.Full as error:
            raise ValueError('A recording action is already pending.') from error
        if not event.wait(10):
            raise RuntimeError('Recording action still pending; wait for the dashboard status.')
        if 'error' in result:
            raise ValueError(result['error'])

    def process_commands(self, sensor):
        while True:
            try:
                action, cfg, event, result = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                if action == 'start':
                    if self.record_phase == 'recording':
                        raise ValueError('Stop the current recording first.')
                    self.cfg = cfg
                    # One interval owns both schedules. No recording decimation.
                    self.rate = 1 / cfg['interval_s']
                    self.schedule_revision += 1
                    self.record_count, self.sd_bytes, self.sd_filename = 0, 0, ''
                    self.sd_phase, self.sd_error, self.sd_error_code = ('starting' if cfg['sd'] else 'off'), '', ''
                    output = ROOT / 'output'
                    output.mkdir(exist_ok=True)
                    name = 'recording_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '.csv'
                    self.record_path = output / name
                    self.record_stream = self.record_path.open('x', encoding='utf-8', newline='')
                    self.record_stream.write(csv_line())
                    self.record_stream.flush()
                    self.card = self.card_factory(sensor, cfg['sd_address']) if cfg['sd'] else None
                    if self.card:
                        try:
                            self.sd_filename = self.card.start(csv_line())
                            self.sd_bytes = self.card.bytes_written
                            self.sd_phase = 'recording'
                        except ReadError as error:
                            self.sd_start_failed(sensor, error)
                    self.record_phase = 'recording'
                    self.record_message = 'Recording to this PC' + (' and SD card.' if self.card else '. SD start failed; PC recording continues.' if self.sd_phase in ('unavailable', 'unconfirmed') else '.')
                else:
                    self.finish_recording()
                with self.lock:
                    self.log(self.record_message)
            except Exception as error:
                result['error'] = str(error)
                if self.card and self.card.filename:
                    self.sd_filename = self.card.filename
                self.record_phase, self.record_message = 'error', str(error)
                self.finish_recording(sync=False)
                raise
            finally:
                event.set()

    def finish_recording(self, sync=True):
        if self.record_phase == 'idle' and not self.record_stream and not self.card:
            return
        try:
            if sync and self.card:
                self.sd_bytes = self.card.finish()
                self.sd_phase = 'closed'
        finally:
            if self.record_stream:
                self.record_stream.close()
                self.record_stream = None
            self.card = None
        if not sync and self.sd_filename:
            self.sd_phase = 'unconfirmed'
            self.record_phase, self.record_message = 'error', 'Connection fault; final SD synchronization was not confirmed. Last verified byte count is retained.'
        elif self.record_phase != 'error':
            self.record_phase = 'stopped'
            self.record_message = 'Recording stopped; CSV retained.' + (' SD synchronized and size verified; file closed.' if self.sd_phase == 'closed' else ' SD was unavailable; PC CSV retained.' if self.sd_phase == 'unavailable' else ' SD close remains unconfirmed.' if self.sd_phase == 'unconfirmed' else '')

    def save_recording(self, row):
        if self.record_phase != 'recording':
            return
        text = csv_line(decorate(row, self.cfg))
        with self.lock:
            self.record_stream.write(text)
            self.record_stream.flush()
            self.record_count += 1
        if self.card and row['status'] == 'ok':
            self.card.write(text)
            self.sd_bytes = self.card.checkpoint()

    def run(self):
        sensor = None
        safe_to_sync = False
        try:
            sensor = self.factory()
            info = sensor.identify()
            output = ROOT / 'output'
            output.mkdir(exist_ok=True)
            path = output / ('attempts_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '.csv')
            with path.open('x', encoding='utf-8', newline='') as trace:
                trace.write(csv_line()); trace.flush()
                with self.lock:
                    self.path, self.info, self.started_ms = path, info, round(time.time() * 1000)
                    self.phase, self.message = 'live', 'Reading temperatures. Start recording when ready.'
                    self.log('100 kHz confirmed; sensor configuration preserved; no USB reset.')
                self.ready.set()
                deadline = time.perf_counter()
                revision = self.schedule_revision
                safe_to_sync = True
                while not self.stop.is_set():
                    self.wake.clear()
                    self.process_commands(sensor)
                    with self.lock:
                        for event in self.record_events:
                            trace.write(csv_line(event))
                        if self.record_events: trace.flush()
                        self.record_events.clear()
                    if revision != self.schedule_revision:
                        revision = self.schedule_revision
                        deadline = time.perf_counter()
                    remaining = deadline - time.perf_counter()
                    if remaining > 0:
                        # Stay responsive to Stop/Disconnect even at a 24-hour interval.
                        self.wake.wait(min(remaining, .1))
                        continue
                    started = time.perf_counter()
                    with self.lock:
                        self.attempts += 1
                        sequence = self.attempts
                    row = dict.fromkeys(FIELDS, '')
                    row.update(sequence=sequence, status='ok')
                    try:
                        row.update(sensor.sample())
                    except ReadError as error:
                        row.update(status='error', error_code=error.code, error=str(error))
                        safe_to_sync = False
                    row.update(timestamp_ms=round(time.time() * 1000), acquisition_ms=round((time.perf_counter() - started) * 1000, 4))
                    with self.lock:
                        self.history.append(row)
                        trace.write(csv_line(decorate(row, self.cfg))); trace.flush()
                        if row['status'] == 'ok':
                            self.valid += 1; self.last_sample_ms = row['timestamp_ms']
                        else:
                            self.failed += 1
                            self.phase, self.message = 'error', row['error']
                            self.log(f"Stopped: {row['error_code']}: {row['error']}")
                    self.save_recording(row)
                    if row['status'] != 'ok':
                        break
                    deadline += 1 / self.rate
                    now = time.perf_counter()
                    if deadline < now:
                        deadline += (math.floor((now - deadline) * self.rate) + 1) / self.rate
        except Exception as error:
            safe_to_sync = False
            with self.lock:
                fault = decorate(dict(sequence=self.attempts, timestamp_ms=round(time.time() * 1000),
                    status='logger_error', error_code=getattr(error, 'code', type(error).__name__), error=str(error)), self.cfg)
                try:
                    if self.record_stream:
                        self.record_stream.write(csv_line(fault)); self.record_stream.flush()
                        self.record_count += 1
                    elif self.record_path:
                        with self.record_path.open('a', encoding='utf-8', newline='') as stream:
                            stream.write(csv_line(fault))
                        self.record_count += 1
                    if self.path:
                        with self.path.open('a', encoding='utf-8', newline='') as stream:
                            for event in self.record_events:
                                stream.write(csv_line(event))
                            self.record_events.clear()
                            stream.write(csv_line(fault))
                except OSError:
                    pass  # The original storage error still remains in state/log.
                self.phase, self.message = 'error', str(error)
                if self.record_path is not None:
                    self.record_phase, self.record_message = 'error', str(error)
                self.log(f"Stopped: {getattr(error, 'code', type(error).__name__)}: {error}")
        finally:
            try:
                self.finish_recording(sync=safe_to_sync)
            except Exception as error:
                self.record_phase, self.record_message = 'error', str(error)
                self.phase, self.message = 'error', str(error)
            close_ok = True
            if sensor:
                try:
                    sensor.close()
                except Exception as error:
                    close_ok = False
                    with self.lock:
                        self.phase, self.message = 'error', 'HID close failed: ' + str(error)
            with self.lock:
                self.ended_ms = round(time.time() * 1000)
                if self.phase != 'error':
                    self.phase, self.message = 'disconnected', 'Disconnected; downloads retained.'
                self.log('HID handle closed. Another reader can connect.' if close_ok else 'HID close failed; check device access before opening another reader.')
            while not self.commands.empty():
                _, _, event, result = self.commands.get_nowait()
                result['error'] = 'Reader stopped before this recording action.'; event.set()
            self.ready.set()


def handler(logger, origin, token):
    base = make_handler(logger, origin, token)
    class Handler(base):
        def do_GET(self):
            if not self.valid_host(): return
            if self.path in ('/', '/logger.html'):
                self.send(200, (ROOT / 'logger.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.path == '/README.md':
                self.send(200, (ROOT / 'README.md').read_bytes(), 'text/plain; charset=utf-8')
            elif self.path == '/api/session':
                self.send(200, {'kind': 'qwiic-temperature-logger', 'token': token,
                    'features': ['bridge-recovery', 'sd-start-fallback', 'separate-sd-status']})
            elif self.path in ('/api/csv', '/api/recording-csv'):
                with logger.lock:
                    path = logger.path if self.path == '/api/csv' else logger.record_path
                    data = path.read_bytes() if path and path.is_file() else None
                self.send(200, data, 'text/csv; charset=utf-8') if data is not None else self.send(404, {'error': 'No CSV yet.'})
            else:
                super().do_GET()

        def do_POST(self):
            if self.path not in ('/api/recording', '/api/recover'): return super().do_POST()
            if not self.valid_host(): return
            if self.headers.get('Origin') != origin or self.headers.get('X-Monitor-Token') != token or self.headers.get('Content-Type') != 'application/json':
                self.send(403, {'error': 'Use this dashboard.'}); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 1024: raise ValueError('Request too large.')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict): raise ValueError('Expected an object.')
                if self.path == '/api/recover':
                    if data: raise ValueError('Recovery takes no parameters.')
                    logger.recover_bridge()
                else:
                    logger.recording_action(data.get('action'), data.get('settings'))
                self.send(200, logger.snapshot())
            except (ValueError, TypeError, RuntimeError) as error:
                self.send(400, {'error': str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--address', type=lambda text: int(text, 0), default=0x60)
    parser.add_argument('--device-index', type=int)
    parser.add_argument('--connect', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not 0x60 <= args.address <= 0x67: parser.error('Invalid port or sensor address.')
    origin = f'http://127.0.0.1:{args.port}'
    logger = Logger(args.address, args.device_index)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(logger, origin, secrets.token_urlsafe(24)))
    print('Temperature logger: ' + origin, flush=True)
    print('Existing native sensor environment reused. Old dashboards preserved. Ctrl+C stops this server.', flush=True)
    try:
        if args.connect: logger.connect()
        if not args.no_browser: webbrowser.open(origin)
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        logger.disconnect(); server.server_close()


if __name__ == '__main__': main()
