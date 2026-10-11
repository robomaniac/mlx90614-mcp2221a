"""Card protocol, recording lifecycle and loopback access checks; no USB access."""
from pathlib import Path
import csv
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import logger
from sdcard import CardBus, OpenLog, ReadError
from recovery import clear_i2c_error, open_sensor_checked


class FakeRecoveryBridge:
    def __init__(self, dirty=False, sticky=False, ack=0, low_line=False):
        self.dirty, self.sticky, self.ack, self.low_line = dirty, sticky, ack, low_line
        self.commands, self.closed = [], False
    def exchange(self, payload, deadline=None):
        self.commands.append(bytes(payload))
        assert payload[0] == 0x10, 'Recovery must not reset USB or access a sensor/card.'
        response = bytearray(64); response[0] = 0x10; response[14] = 118
        response[22:24] = bytes((0 if self.low_line else 1, 1))
        if len(payload) >= 3 and payload[2] == 0x10:
            response[2] = self.ack
            if not self.sticky: self.dirty = False
        if self.dirty: response[8] = 0x25; response[20] = 64
        return bytes(response)
    def close(self): self.closed = True


class RecoveryTests(unittest.TestCase):
    def test_dirty_bridge_cleared_once_and_verified_independently_even_without_ack(self):
        for ack in (0, 0x10, 0x11):
            bridge = FakeRecoveryBridge(dirty=True, ack=ack)
            clear_i2c_error(bridge)
            self.assertEqual(bridge.commands, [b'\x10', b'\x10\x00\x10', b'\x10'])
            self.assertFalse(bridge.dirty)
    def test_idle_bridge_does_not_cancel(self):
        bridge = FakeRecoveryBridge(); clear_i2c_error(bridge)
        self.assertEqual(bridge.commands, [b'\x10'])
    def test_unreleased_bus_stops_after_one_cancellation(self):
        for bridge in (FakeRecoveryBridge(dirty=True, sticky=True), FakeRecoveryBridge(low_line=True)):
            with self.assertRaises(ReadError) as caught: clear_i2c_error(bridge)
            self.assertEqual(caught.exception.code, 'RECOVERY_BUSY')
            self.assertEqual(bridge.commands.count(b'\x10\x00\x10'), 1)
    def test_dirty_startup_refused_before_config_or_identity_read(self):
        bridge = FakeRecoveryBridge(dirty=True)
        with patch('recovery.open_bridge', return_value=bridge):
            with self.assertRaises(ReadError) as caught: open_sensor_checked(96)
        self.assertEqual(caught.exception.code, 'BRIDGE_DIRTY')
        self.assertEqual(bridge.commands, [b'\x10']); self.assertTrue(bridge.closed)


class FakeCardBus:
    def __init__(self):
        self.files, self.commands = {}, []
        self.open = False
        self.reply = b'\x07'
        self.selected = ''
        self.drop = False
        self.bad_status = False

    def write(self, address, data):
        assert address == 42 and 1 <= len(data) <= 32
        self.commands.append(data)
        reg, arg = data[0], data[1:]
        name = arg.decode('ascii') if reg in (6, 11, 13, 9) else ''
        self.reply = b'\x05' if self.bad_status else b'\x07'
        if reg in (0, 1, 2, 3): self.reply = bytes([{0: 0x78, 1: 1, 2: 3, 3: 1}[reg]])
        elif reg == 6:
            if name in self.files: self.reply = b'\x05'
            else: self.files[name] = b''
        elif reg == 11: self.selected, self.open = name, True
        elif reg == 12:
            assert self.open
            if not self.drop: self.files[self.selected] += arg
        elif reg == 13:
            self.open = False
            self.reply = len(self.files.get(name, b'')).to_bytes(4, 'big')
        elif reg == 9: self.reply = self.files[name]
        else: assert reg in (8, 17), 'Unsafe command'

    def read(self, address, length):
        data = self.reply[:length]
        if len(self.reply) > length: self.reply = self.reply[length:]
        assert len(data) == length
        return data


class CardTests(unittest.TestCase):
    def test_unsupported_firmware_rejected_before_any_file_command(self):
        class LegacyCard(FakeCardBus):
            def __init__(self, major): super().__init__(); self.major = major
            def write(self, address, data):
                super().write(address, data)
                if data[0] == 2: self.reply = bytes([self.major])
        for major in (1, 2, 4):
            bus = LegacyCard(major); card = OpenLog(bus)
            with self.assertRaises(ReadError) as caught: card.start('header\r\n')
            self.assertEqual(caught.exception.code, 'SD_FIRMWARE')
            self.assertEqual([p[0] for p in bus.commands], [0, 1, 2, 3])
            self.assertEqual(bus.files, {})
            self.assertFalse(card.active)

    def test_read_waits_for_stretched_transfer_before_fetching_data(self):
        class Bridge:
            closed = False
            def __init__(self): self.device = self; self.commands = []; self.states = iter((0x50, 0x50, 0x55))
            def write(self, data): self.commands.append(data[1]); return 65
            def read(self, length, wait): return bytes([0x91]) + bytes(63)
            def exchange(self, payload, deadline):
                self.commands.append(payload[0]); r = bytearray(64); r[0] = payload[0]
                if payload[0] == 0x10: r[8] = next(self.states)
                else: r[2:5] = bytes((0x55, 1, 0x17))
                return r
        bridge = Bridge()
        self.assertEqual(CardBus(bridge).read(42, 1), b'\x17')
        self.assertEqual(bridge.commands, [0x91, 0x10, 0x10, 0x10, 0x40])

    def test_stretched_read_timeout_does_not_reset_cancel_or_fetch(self):
        class Bridge:
            closed = False
            def __init__(self): self.device = self; self.commands = []
            def write(self, data): self.commands.append(data[1]); return 65
            def read(self, length, wait): return bytes([0x91]) + bytes(63)
            def exchange(self, payload, deadline):
                self.commands.append(payload[0]); r = bytearray(64); r[0] = 0x10; r[8] = 0x50; return r
        bridge = Bridge(); bus = CardBus(bridge, timeout_ms=5)
        with self.assertRaises(ReadError) as caught: bus.read(42, 1)
        self.assertEqual(caught.exception.code, 'SD_TIMEOUT')
        self.assertTrue(bus.poisoned)
        self.assertTrue(set(bridge.commands) <= {0x91, 0x10})

    def test_ready_read_still_rejects_invalid_data_and_address_nack(self):
        class Bridge:
            closed = False
            def __init__(self, nack=False): self.device = self; self.nack = nack; self.commands = []
            def write(self, data): self.commands.append(data[1]); return 65
            def read(self, length, wait): return bytes([0x91]) + bytes(63)
            def exchange(self, payload, deadline):
                self.commands.append(payload[0]); r = bytearray(64); r[0] = payload[0]
                if payload[0] == 0x10: r[8] = 0x25 if self.nack else 0x55
                else: r[1:4] = bytes((0x41, 0x50, 127))
                return r
        for nack, code in ((False, 'SD_I2C_DATA'), (True, 'SD_I2C_STATE')):
            bridge = Bridge(nack)
            with self.assertRaises(ReadError) as caught: CardBus(bridge).read(42, 1)
            self.assertEqual(caught.exception.code, code)
            if nack: self.assertNotIn(0x40, bridge.commands)

    def test_new_file_unicode_chunks_sync_size_close_and_readback(self):
        bus = FakeCardBus(); card = OpenLog(bus)
        card.start('head\r\n', 'T123ABCD.CSV'); card.write('é' * 40)
        self.assertEqual(card.checkpoint(), 86); self.assertTrue(bus.open)
        self.assertEqual(card.finish(), 86); self.assertFalse(bus.open)
        self.assertEqual(card.read_file(86), ('head\r\n' + 'é' * 40).encode())
        self.assertTrue(all(len(p) <= 32 for p in bus.commands))

    def test_existing_file_never_appended(self):
        bus = FakeCardBus(); bus.files['T123ABCD.CSV'] = b'preserve'
        with self.assertRaisesRegex(ReadError, 'status'): OpenLog(bus).start('h', 'T123ABCD.CSV')
        self.assertEqual(bus.files['T123ABCD.CSV'], b'preserve')
        self.assertNotIn(11, [p[0] for p in bus.commands])

    def test_silent_write_loss_rejected_by_size(self):
        bus = FakeCardBus(); card = OpenLog(bus); card.start('h')
        bus.drop = True; card.write('new')
        with self.assertRaisesRegex(ReadError, 'Expected 4'): card.checkpoint()

    def test_mutation_response_read_directly(self):
        bus = FakeCardBus(); card = OpenLog(bus); card.start('h')
        bus.bad_status = True
        with self.assertRaises(ReadError): card.command(17)
        self.assertEqual(bus.commands[-1], b'\x11')

    def test_delete_config_reset_paths_and_names_rejected(self):
        card = OpenLog(FakeCardBus())
        for reg in (5, 15, 16, 30, 112):
            with self.assertRaises(ValueError): card.command(reg)
        for name in ('../../x.csv', 'T123ABCD.CSV/other', 'test.csv'):
            with self.assertRaises(ValueError): card.name(name)
        with self.assertRaises(ValueError): CardBus.address(0x60)

    def test_nul_and_readback_while_open_rejected(self):
        card = OpenLog(FakeCardBus()); card.start('h')
        with self.assertRaises(ValueError): card.write('a\0b')
        with self.assertRaises(ValueError): card.read_file(1)

    def test_address_nack_stops_without_reset_or_cancel(self):
        class Bridge:
            def __init__(self): self.closed = False; self.commands = []; self.device = self
            def write(self, data): self.commands.append(data[1]); return 65
            def read(self, length, wait): return bytes([0x90]) + bytes(63)
            def exchange(self, payload, deadline):
                self.commands.append(payload[0]); r = bytearray(64); r[0] = payload[0]; r[20] = 64; return r
        bridge = Bridge()
        with self.assertRaises(ReadError) as caught: CardBus(bridge).write(42, b'\x00')
        self.assertEqual(caught.exception.code, 'SD_I2C_STATE')
        self.assertEqual(bridge.commands, [0x90, 0x10])


class SettingsTests(unittest.TestCase):
    def test_interval_bounds_poll_rate_names_and_types(self):
        self.assertEqual(logger.settings({'interval_s': .25}, 4)['interval_s'], .25)
        self.assertEqual(logger.settings({'interval_s': 86400}, 1)['interval_s'], 86400)
        self.assertEqual(logger.settings({'interval_s': .25}, 2)['interval_s'], .25)
        for data in ({'interval_s': .24}, {'interval_s': True}, {'interval_s': float('nan')},
                     {'interval_s': 86401}, {'probe_name': 'x\n'}, {'probe_name': ''},
                     {'probe_name': 'a' * 41}, {'sd': 1}, {'extra': 1}):
            with self.assertRaises(ValueError): logger.settings(data, 2)

    def test_csv_timestamps_units_error_and_formula_escape(self):
        cfg = {**logger.DEFAULTS, 'probe_name': '=Probe, "A"'}
        row = logger.decorate(dict(sequence=1, timestamp_ms=1000, status='ok', hot_c=100, cold_c=-40), cfg)
        parsed = list(csv.DictReader(io.StringIO(logger.csv_line() + logger.csv_line(row))))[0]
        self.assertEqual(parsed['hot_f'], '212.0'); self.assertEqual(parsed['cold_f'], '-40.0')
        self.assertEqual(parsed['timestamp_utc'], '1970-01-01T00:00:01.000Z')
        self.assertEqual(parsed['probe_name'], "'=Probe, \"A\"")
        err = logger.decorate(dict(sequence=2, timestamp_ms=2000, status='error', error='bad, "read"\nagain'), cfg)
        self.assertNotIn('hot_f', err)
        self.assertEqual(list(csv.DictReader(io.StringIO(logger.csv_line()+logger.csv_line(err))))[0]['error'], err['error'])


class FakeSensor:
    def __init__(self): self.closed = False; self.fail = False; self.bridge = FakeRecoveryBridge()
    def identify(self): return {'device_id': '4014', 'address': 96}
    def sample(self):
        if self.bridge.dirty: raise ReadError('I2C_COMMAND', 'Bridge still has the SD address error')
        if self.fail: raise ReadError('INPUT_RANGE', 'Probe fault')
        return dict(hot_c=23.5, cold_c=24., hot_raw='0178', cold_raw='0180', sensor_status=0)
    def close(self): self.closed = True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(logger, 'ROOT', Path(self.temp.name)); self.root_patch.start()
        self.sensor = FakeSensor(); self.bus = FakeCardBus()
        self.monitor = logger.Logger(factory=lambda: self.sensor, card_factory=lambda sensor, address: OpenLog(self.bus, address))
    def tearDown(self):
        self.monitor.disconnect(); self.root_patch.stop(); self.temp.cleanup()
    def wait_for(self, predicate):
        end = time.monotonic()+3
        while not predicate():
            if time.monotonic()>end: self.fail('Timed out')
            time.sleep(.01)
    def test_sd_start_record_stop_closes_and_preserves_full_csv(self):
        self.monitor.connect(4)
        self.monitor.recording_action('start', {'sd': True, 'interval_s': .25})
        self.wait_for(lambda: self.monitor.record_count >= 2)
        with self.assertRaises(ValueError): self.monitor.set_rate(2)
        self.monitor.recording_action('stop')
        self.assertFalse(self.bus.open); self.assertIn('file closed', self.monitor.record_message)
        data = self.monitor.record_path.read_bytes()
        self.assertEqual(data, self.bus.files[self.monitor.sd_filename])
        self.monitor.disconnect(); self.assertTrue(self.sensor.closed)
        self.assertEqual(self.monitor.snapshot()['failed'], 0)
    def test_read_error_is_recorded_and_no_sd_sync(self):
        self.monitor.connect(4); self.monitor.recording_action('start', {'interval_s': .25, 'sd': True})
        self.wait_for(lambda: self.monitor.record_count == 1)
        self.sensor.fail = True
        self.wait_for(lambda: not self.monitor.thread.is_alive())
        rows = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text(encoding='utf-8'))))
        self.assertEqual([r['status'] for r in rows], ['ok', 'error'])
        self.assertEqual(rows[-1]['error_code'], 'INPUT_RANGE')
        self.assertEqual(self.monitor.record_phase, 'error')
        self.assertIn('not confirmed', self.monitor.record_message)
    def test_every_poll_saved_at_custom_interval_without_decimation(self):
        self.monitor.connect(2)
        self.monitor.recording_action('start', {'interval_s': .4, 'sd': True})
        self.assertEqual(self.monitor.rate, 2.5)
        self.wait_for(lambda: self.monitor.record_count >= 4)
        self.monitor.recording_action('stop')
        rows = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text())))
        sequences = [int(row['sequence']) for row in rows]
        self.assertEqual(sequences, list(range(sequences[0], sequences[-1] + 1)))
        self.assertEqual(self.monitor.record_count, len(rows))
        self.assertEqual(self.monitor.record_path.read_bytes(), self.bus.files[self.monitor.sd_filename])
    def test_hourly_polling_saves_first_poll_and_stop_remains_responsive(self):
        self.monitor.connect(2)
        self.monitor.recording_action('start', {'interval_s': 3600, 'sd': True})
        self.wait_for(lambda: self.monitor.record_count == 1)
        self.assertEqual(self.monitor.rate, 1 / 3600)
        attempts = self.monitor.attempts
        time.sleep(.2)
        self.assertEqual(self.monitor.attempts, attempts)
        started = time.monotonic()
        self.monitor.recording_action('stop')
        self.monitor.disconnect()
        self.assertLess(time.monotonic() - started, 1)
        self.assertFalse(self.bus.open)
        self.assertTrue(self.sensor.closed)
    def test_invalid_interval_does_not_change_rate_or_create_recording(self):
        self.monitor.connect(2)
        for interval in (.24, 86401, float('nan')):
            with self.assertRaises(ValueError):
                self.monitor.recording_action('start', {'interval_s': interval, 'sd': True})
        self.assertEqual(self.monitor.rate, 2)
        self.assertIsNone(self.monitor.record_path)
        self.assertEqual(self.bus.files, {})
    def test_silent_card_write_failure_stops_and_retains_fault_csv(self):
        self.monitor.connect(4); self.monitor.recording_action('start', {'interval_s': .25, 'sd': True})
        self.bus.drop = True
        self.wait_for(lambda: not self.monitor.thread.is_alive())
        rows = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text())))
        self.assertEqual(rows[-1]['status'], 'logger_error'); self.assertEqual(rows[-1]['error_code'], 'SD_SIZE')
        self.assertEqual(self.monitor.phase, 'error'); self.assertTrue(self.sensor.closed)
    def test_no_reader_no_recording_action(self):
        with self.assertRaises(ValueError): self.monitor.recording_action('start', {})
    def test_failed_sd_start_retained_in_recording_csv(self):
        self.bus.bad_status = True
        self.monitor.connect(4)
        self.monitor.recording_action('start', {'sd': True, 'interval_s': .25})
        self.wait_for(lambda: self.monitor.record_count >= 3)
        self.monitor.recording_action('stop')
        rows = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text(encoding='utf-8'))))
        self.assertEqual(rows[0]['status'], 'logger_error')
        self.assertEqual(rows[0]['error_code'], 'SD_COMMAND')
        self.assertTrue(all(r['status'] == 'ok' for r in rows[1:]))
        self.assertEqual(self.monitor.phase, 'live')
        self.assertEqual(self.monitor.snapshot()['recording']['sd_phase'], 'unavailable')
    def test_missing_sd_clears_owned_error_keeps_pc_recording_and_can_restart_without_sd(self):
        sensor = self.sensor
        class MissingCard:
            filename = ''; bytes_written = 0
            def start(self, header):
                sensor.bridge.dirty = True
                raise ReadError('SD_I2C_STATE', '10 00 00 00 00 00 00 00 25 00 00 00 00 00 76 00 00 00 00 00 40 00 01 01 00 00', True)
        self.monitor.card_factory = lambda sensor, address: MissingCard()
        self.monitor.connect(4); self.monitor.recording_action('start', {'sd': True, 'interval_s': .25})
        self.wait_for(lambda: self.monitor.record_count >= 4)
        self.monitor.recording_action('stop')
        recorded = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text())))
        attempted = list(csv.DictReader(io.StringIO(self.monitor.path.read_text())))
        self.assertEqual(recorded[0]['error_code'], 'SD_I2C_STATE')
        self.assertTrue(any(r['error'] == recorded[0]['error'] for r in attempted))
        self.assertTrue(all(r['status'] == 'ok' for r in recorded[1:]))
        self.assertEqual(sensor.bridge.commands.count(b'\x10\x00\x10'), 1)
        self.assertEqual(self.monitor.failed, 0); self.assertEqual(self.monitor.phase, 'live')
        old_path = self.monitor.record_path
        self.monitor.recording_action('start', {'sd': False, 'interval_s': .25})
        self.wait_for(lambda: self.monitor.record_count >= 2)
        self.monitor.recording_action('stop')
        self.assertTrue(old_path.exists()); self.assertEqual(self.monitor.sd_phase, 'off')
    def test_failed_recovery_retains_both_errors_and_stops(self):
        sensor = self.sensor; sensor.bridge.sticky = True
        class MissingCard:
            filename = ''; bytes_written = 0
            def start(self, header):
                sensor.bridge.dirty = True
                raise ReadError('SD_I2C_STATE', 'missing SD address', True)
        self.monitor.card_factory = lambda sensor, address: MissingCard()
        self.monitor.connect(4)
        with self.assertRaises(ValueError): self.monitor.recording_action('start', {'sd': True})
        self.wait_for(lambda: not self.monitor.thread.is_alive())
        rows = list(csv.DictReader(io.StringIO(self.monitor.record_path.read_text())))
        self.assertEqual([r['error_code'] for r in rows], ['SD_I2C_STATE', 'RECOVERY_BUSY'])
        self.assertEqual(self.monitor.phase, 'error'); self.assertTrue(sensor.closed)
    def test_partial_sd_start_keeps_pc_csv_without_claiming_sd_closed(self):
        self.bus.drop = True
        self.monitor.connect(4); self.monitor.recording_action('start', {'sd': True, 'interval_s': .25})
        self.wait_for(lambda: self.monitor.record_count >= 3)
        self.monitor.recording_action('stop')
        self.assertEqual(self.monitor.phase, 'live')
        r = self.monitor.snapshot()['recording']
        self.assertEqual(r['sd_phase'], 'unconfirmed'); self.assertTrue(r['sd_filename'])
        self.assertNotIn('file closed', r['message'])
        self.assertIn('SD_SIZE', self.monitor.record_path.read_text())
    def test_missing_hid_reply_never_triggers_recovery(self):
        class MissingReply:
            filename = ''; bytes_written = 0
            def start(self, header): raise ReadError('HID_TIMEOUT', 'No USB reply', True)
        self.monitor.card_factory = lambda sensor, address: MissingReply()
        self.monitor.connect(4)
        with self.assertRaises(ValueError): self.monitor.recording_action('start', {'sd': True})
        self.wait_for(lambda: not self.monitor.thread.is_alive())
        self.assertEqual(self.sensor.bridge.commands, [])
        self.assertIn('HID_TIMEOUT', self.monitor.record_path.read_text())
    def test_sensor_connect_failure_does_not_invent_an_sd_session_result(self):
        self.monitor.cfg['sd'] = True
        self.monitor.factory = lambda: (_ for _ in ()).throw(ReadError('BRIDGE_DIRTY', 'dirty bridge'))
        self.monitor.connect(2); self.wait_for(lambda: not self.monitor.thread.is_alive())
        r = self.monitor.snapshot()['recording']
        self.assertEqual(r['phase'], 'idle'); self.assertEqual(r['sd_phase'], 'off')
        self.assertFalse(r['available'])
    def test_manual_recovery_preserves_csv_and_refuses_live_reader(self):
        bridge = FakeRecoveryBridge(dirty=True)
        self.monitor.bridge_factory = lambda: bridge
        self.monitor.connect(4)
        with self.assertRaises(ValueError): self.monitor.recover_bridge()
        self.assertEqual(bridge.commands, [])
        self.monitor.disconnect(); path = self.monitor.path; data = path.read_bytes()
        self.monitor.recover_bridge()
        self.assertEqual(self.monitor.phase, 'disconnected'); self.assertTrue(bridge.closed)
        self.assertEqual(self.monitor.path, path); self.assertEqual(path.read_bytes(), data)
    def test_loopback_token_and_origin_guards(self):
        origin = 'http://127.0.0.1:9876'
        server = logger.ThreadingHTTPServer(('127.0.0.1', 0), logger.handler(self.monitor, origin, 'test-only-token'))
        # The guard expects this exact Host, independent of the ephemeral test socket.
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        try:
            headers = {'Host':'127.0.0.1:9876','Content-Type':'application/json'}
            for route in ('/api/recording', '/api/recover'):
                connection.request('POST',route,'{}',headers)
                response=connection.getresponse(); self.assertEqual(response.status,403); response.read()
            headers.update(Origin=origin, **{'X-Monitor-Token':'test-only-token'})
            connection.request('POST','/api/recording','[]',headers)
            response=connection.getresponse(); self.assertEqual(response.status,400); response.read()
            bridge = FakeRecoveryBridge(dirty=True)
            self.monitor.bridge_factory = lambda: bridge
            connection.request('POST','/api/recover','{"extra":true}',headers)
            response=connection.getresponse(); self.assertEqual(response.status,400); response.read()
            self.assertEqual(bridge.commands, [])
            connection.request('POST','/api/recover','{}',headers)
            response=connection.getresponse(); self.assertEqual(response.status,200)
            self.assertEqual(json.loads(response.read())['phase'],'disconnected')
            self.assertEqual(bridge.commands.count(b'\x10\x00\x10'),1)
            connection.request('GET','/api/session',headers={'Host':'127.0.0.1:9876'})
            response=connection.getresponse(); self.assertEqual(json.loads(response.read())['kind'],'qwiic-temperature-logger')
            (Path(self.temp.name) / 'README.md').write_text('Local operating guide', encoding='utf-8')
            connection.request('GET','/README.md',headers={'Host':'127.0.0.1:9876'})
            response=connection.getresponse(); self.assertEqual(response.status,200)
            self.assertEqual(response.getheader('Content-Type'),'text/plain; charset=utf-8')
            self.assertEqual(response.read(),b'Local operating guide')
        finally:
            connection.close(); server.shutdown(); worker.join(2); server.server_close()


if __name__ == '__main__': unittest.main()
